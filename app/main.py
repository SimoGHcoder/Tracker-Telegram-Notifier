import secrets
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.background import BackgroundScheduler
from app.config import load_config, save_config, load_users_data, save_users_data, APP_VERSION
from app.tracker import ReleaseTracker
from app.telegram_bot import TelegramNotifier

app = FastAPI(title="Tracker Release Multi-Profilo")
tracker = ReleaseTracker()
scheduler = BackgroundScheduler()
pending_telegram_codes = {}

def scheduled_check():
    tracker.check_for_releases()

@app.on_event("startup")
def startup_event():
    config = load_config()
    hours = config.get("check_interval_hours", 4)
    scheduler.add_job(scheduled_check, "interval", hours=hours, id="release_check_job")
    scheduler.start()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("app/static/index.html")

@app.get("/api/version")
async def get_version():
    return {"version": APP_VERSION}

@app.get("/api/config")
async def get_config():
    config = load_config()
    users = load_users_data()
    public_config = {**config, **users}
    nuvio_config = dict(public_config.get("nuvio") or {})
    telegram_config = dict(public_config.get("telegram") or {})
    nuvio_config["password_configured"] = bool(nuvio_config.pop("password", ""))
    telegram_config["bot_token_configured"] = bool(telegram_config.pop("bot_token", ""))
    public_config["nuvio"] = nuvio_config
    public_config["telegram"] = telegram_config
    return public_config

@app.post("/api/config")
async def save_config_endpoint(data: dict):
    selected_addons = data.get("selected_addons")
    if selected_addons is not None and (
        not isinstance(selected_addons, list)
        or not all(isinstance(url, str) for url in selected_addons)
    ):
        raise HTTPException(status_code=400, detail="La selezione degli addon non è valida.")

    config = load_config()
    users = load_users_data()

    config["ui_language"] = data.get("ui_language", config.get("ui_language", "it"))
    config["dubbing_language"] = data.get("dubbing_language", config.get("dubbing_language", "ita"))
    
    new_interval = data.get("check_interval_hours")
    if new_interval and new_interval != config.get("check_interval_hours"):
        config["check_interval_hours"] = new_interval
        try:
            scheduler.reschedule_job("release_check_job", trigger="interval", hours=new_interval)
        except Exception:
            pass

    nuvio_updates = data.get("nuvio")
    if nuvio_updates is not None:
        if not isinstance(nuvio_updates, dict):
            raise HTTPException(status_code=400, detail="La configurazione Nuvio non è valida.")
        config.setdefault("nuvio", {}).update(nuvio_updates)

    save_config(config)

    if "active_profile_id" in data:
        users["active_profile_id"] = data["active_profile_id"]

    if "inherit_main_telegram" in data:
        profile_id = str(users.get("active_profile_id", 1))
        users.setdefault("inherit_main_telegram", {})[profile_id] = data["inherit_main_telegram"]

    if "selected_addons" in data:
        profile_id = str(users.get("active_profile_id", 1))
        users.setdefault("selected_addons", {})[profile_id] = list(dict.fromkeys(selected_addons))
    
    save_users_data(users)
    tracker.reload_config()
    return {"status": "success"}

@app.get("/api/addons")
async def get_addons():
    try:
        addons = tracker.get_nuvio_addons()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    users = load_users_data()
    profile_id = str(users.get("active_profile_id", 1))
    selected_by_profile = users.get("selected_addons", {})
    selected_addons = selected_by_profile.get(profile_id)
    if selected_addons is None:
        selected_addons = [addon["url"] for addon in addons]

    return {"addons": addons, "selected_addons": selected_addons}

@app.get("/api/dashboard")
async def get_dashboard_data():
    config = load_config()
    users = load_users_data()
    active_profile_id = str(users.get("active_profile_id", 1))
    
    history = tracker.get_nuvio_history() or []
    library = tracker.get_unified_library() or []
    notification_targets = tracker.merge_notification_targets(library, history)
    active_notifications_count = sum(
        1 for item in notification_targets if item.get("notifications_enabled", True)
    )

    profiles_telegram = users.get("profiles_telegram", {})
    telegram_usernames = users.get("telegram_usernames", {})
    inherit_prefs = users.get("inherit_main_telegram", {})
    
    is_p1 = (active_profile_id == "1")
    use_inherit = inherit_prefs.get(active_profile_id, True) if not is_p1 else False
    
    if is_p1:
        tg_status = telegram_usernames.get("1") or profiles_telegram.get("1") or config.get("telegram", {}).get("chat_id") or "Non collegato"
    else:
        if use_inherit:
            main_name = telegram_usernames.get("1") or profiles_telegram.get("1") or "Profilo Principale"
            tg_status = f"{main_name} (Ereditato)"
        else:
            tg_status = telegram_usernames.get(active_profile_id) or profiles_telegram.get(active_profile_id) or "Non collegato"

    return {
        "total_history_shows": len(history),
        "total_library_items": len(library),
        "total_notification_items": len(notification_targets),
        "active_notifications": active_notifications_count,
        "check_interval_hours": config.get("check_interval_hours", 4),
        "dubbing_language": config.get("dubbing_language", "ita").upper(),
        "telegram_status": tg_status,
        "recent_releases": history[:5],
        "version": APP_VERSION
    }

@app.post("/api/reset")
async def reset_application(data: dict | None = None):
    try:
        remove_telegram_token = (data or {}).get("remove_telegram_token", True)
        if not isinstance(remove_telegram_token, bool):
            raise HTTPException(status_code=400, detail="La scelta sul token Telegram non è valida.")

        current_config = load_config()
        bot_token = "" if remove_telegram_token else current_config.get("telegram", {}).get("bot_token", "")
        default_config = {
            "ui_language": "it",
            "dubbing_language": "ita",
            "check_interval_hours": 4,
            "telegram": {
                "bot_token": bot_token
            },
            "first_run_completed": False,
            "manual_shows": [],
            "nuvio": {
                "email": "",
                "password": "",
                "profile_id": 1
            }
        }
        save_config(default_config)
        save_users_data({})
        tracker.reload_config()
        return {"status": "success", "message": "Applicazione resettata correttamente."}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Errore durante il reset: {str(e)}")

@app.get("/api/profiles")
async def get_profiles():
    return tracker.get_nuvio_profiles()

@app.post("/api/select-profile")
async def select_profile(data: dict):
    profile_id = data.get("profile_id", 1)
    
    users = load_users_data()
    users["active_profile_id"] = profile_id
    save_users_data(users)
    
    config = load_config()
    config.setdefault("nuvio", {})["profile_id"] = profile_id
    save_config(config)

    tracker.reload_config()
    return {"status": "success", "profile_id": profile_id}

@app.get("/api/library")
async def get_library():
    return tracker.get_unified_library()

@app.get("/api/history")
async def get_history():
    return tracker.get_nuvio_history()

@app.post("/api/toggle-notification")
async def toggle_notification(data: dict):
    content_id = data.get("content_id")
    enabled = data.get("enabled", True)
    users = load_users_data()
    users.setdefault("notification_prefs", {})[content_id] = enabled
    save_users_data(users)
    return {"status": "success"}

@app.post("/api/toggle-all-notifications")
async def toggle_all_notifications(data: dict):
    enabled = data.get("enabled", True)
    scope = data.get("scope")
    if scope not in {"library", "history"}:
        raise HTTPException(status_code=400, detail="La scheda delle notifiche non è valida.")
    tracker.toggle_all_notifications(enabled, scope)
    return {"status": "success", "scope": scope, "enabled": enabled}

@app.post("/api/check-now")
async def check_now():
    return tracker.check_for_releases()

@app.post("/api/telegram/start-connect")
async def start_telegram_connect():
    config = load_config()
    users = load_users_data()
    bot_token = config.get("telegram", {}).get("bot_token", "")
    if not bot_token:
        raise HTTPException(status_code=400, detail="Bot Token Telegram non configurato.")

    notifier = TelegramNotifier(bot_token=bot_token, chat_id="")
    bot_username = notifier.get_bot_username()
    if not bot_username:
        raise HTTPException(status_code=400, detail="Token Telegram non valido o bot non raggiungibile.")

    profile_id = str(users.get("active_profile_id", 1))
    code = secrets.token_hex(4)
    pending_telegram_codes[code] = {"profile_id": profile_id}
    
    return {"code": code, "deep_link": f"https://t.me/{bot_username}?start={code}"}

@app.post("/api/telegram/token")
async def save_telegram_token(data: dict):
    bot_token = data.get("bot_token")
    if not isinstance(bot_token, str):
        raise HTTPException(status_code=400, detail="Il token Telegram non è valido.")

    bot_token = bot_token.strip()
    bot_username = None
    if bot_token:
        bot_username = TelegramNotifier(bot_token=bot_token).get_bot_username()
        if not bot_username:
            raise HTTPException(status_code=400, detail="Token Telegram non valido o bot non raggiungibile.")

    config = load_config()
    config.setdefault("telegram", {})["bot_token"] = bot_token
    save_config(config)
    tracker.reload_config()
    return {"status": "success", "configured": bool(bot_token), "bot_username": bot_username}

@app.get("/api/telegram/check-link/{code}")
async def check_telegram_link(code: str):
    config = load_config()
    users = load_users_data()
    bot_token = config.get("telegram", {}).get("bot_token", "")
    if not bot_token:
        return {"status": "pending"}

    notifier = TelegramNotifier(bot_token=bot_token, chat_id="")
    chat_id, user_display_name = notifier.resolve_start_code_with_user(code)

    if chat_id:
        pending_info = pending_telegram_codes.get(code, {})
        profile_id = str(pending_info.get("profile_id") or users.get("active_profile_id", "1"))
        
        users.setdefault("profiles_telegram", {})[profile_id] = str(chat_id)
        if user_display_name:
            users.setdefault("telegram_usernames", {})[profile_id] = user_display_name
            
        users.setdefault("inherit_main_telegram", {})[profile_id] = False
        save_users_data(users)
        tracker.reload_config()
        
        if code in pending_telegram_codes:
            del pending_telegram_codes[code]

        return {"status": "success", "chat_id": chat_id, "profile_id": profile_id}

    return {"status": "pending"}

@app.post("/api/telegram/reset-profile")
async def reset_telegram_profile():
    users = load_users_data()
    config = load_config()
    active_profile_id = str(users.get("active_profile_id", 1))
    
    profiles_telegram = users.get("profiles_telegram", {})
    telegram_usernames = users.get("telegram_usernames", {})
    inherit_prefs = users.get("inherit_main_telegram", {})
    
    chat_id_to_notify = None
    if not inherit_prefs.get(active_profile_id, True) and active_profile_id != "1":
        chat_id_to_notify = profiles_telegram.get(active_profile_id)
    elif active_profile_id == "1":
        chat_id_to_notify = profiles_telegram.get("1") or config.get("telegram", {}).get("chat_id")
        
    bot_token = config.get("telegram", {}).get("bot_token", "")
    if bot_token and chat_id_to_notify:
        try:
            notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id_to_notify)
            notifier.send_message(
                chat_id_to_notify, 
                "⚠️ <b>TelegramTrackerNotifier (TTN)</b>\n\nQuesto account Telegram è stato <b>scollegato con successo</b> dal profilo Nuvio."
            )
        except Exception as e:
            print(f"Errore invio notifica di disconnessione: {e}")

    if active_profile_id in profiles_telegram:
        del profiles_telegram[active_profile_id]
    if active_profile_id in telegram_usernames:
        del telegram_usernames[active_profile_id]
        
    if active_profile_id != "1":
        inherit_prefs[active_profile_id] = True
    elif "1" in inherit_prefs:
        del inherit_prefs["1"]
        
    save_users_data(users)
    tracker.reload_config()
    return {"status": "success", "message": f"Telegram resettato per il profilo {active_profile_id}"}

@app.post("/api/telegram/test-notification")
async def send_test_notification():
    config = load_config()
    users = load_users_data()
    
    bot_token = config.get("telegram", {}).get("bot_token", "")
    if not bot_token:
        raise HTTPException(status_code=400, detail="Bot Token Telegram non configurato.")
    
    active_profile_id = str(users.get("active_profile_id", 1))
    profiles_telegram = users.get("profiles_telegram", {})
    inherit_prefs = users.get("inherit_main_telegram", {})
    
    chat_id = None
    use_inherit = inherit_prefs.get(active_profile_id, True) if active_profile_id != "1" else False

    if active_profile_id == "1" or use_inherit:
        chat_id = profiles_telegram.get("1") or config.get("telegram", {}).get("chat_id")
    else:
        chat_id = profiles_telegram.get(active_profile_id)
    
    if not chat_id:
        return {"success": False, "message": "❌ Nessun Chat ID collegato o ereditabile per questo profilo."}

    profiles_list = tracker.get_nuvio_profiles() or []
    profile_name = next((p.get("name") for p in profiles_list if str(p.get("id")) == str(active_profile_id)), f"Profilo {active_profile_id}")

    notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id)
    text = f"🔔 <b>Test Notifica</b> per il profilo <b>{profile_name}</b> completato con successo!"
    success = notifier.send_message(chat_id, text)
    
    if success:
        return {"success": True, "message": "✅ Notifica di test inviata con successo!"}
    else:
        return {"success": False, "message": "❌ Errore durante l'invio della notifica."}

@app.post("/api/nuvio/test-credentials")
async def test_nuvio_credentials(data: dict):
    email = data.get("email")
    password = data.get("password")
    
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email e password sono obbligatorie.")
    
    try:
        temp_tracker = ReleaseTracker()
        access_token = temp_tracker.get_nuvio_access_token(email, password)
        if not access_token:
            return {"status": "error", "message": "Autenticazione fallita: credenziali non valide o errore di connessione."}

        profiles = temp_tracker.get_nuvio_profiles(access_token=access_token)
        
        if isinstance(profiles, list):
            return {
                "status": "success", 
                "message": f"Credenziali valide! Trovati {len(profiles)} profili.",
                "profiles": profiles
            }
        else:
            return {"status": "error", "message": "Autenticazione fallita: credenziali non valide o errore di connessione."}
    except Exception as e:
        return {"status": "error", "message": f"Errore di connessione a Nuvio: {str(e)}"}