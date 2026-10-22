from typing import Any, Dict, List, Optional
import re
from urllib.parse import urlsplit
from urllib.parse import quote
import requests
from app.config import load_config, load_users_data, save_users_data
from app.telegram_bot import TelegramNotifier


class ReleaseTracker:
  NUVIO_PUBLISHABLE_KEY = "sb_publishable_1Clq8rlTVACkdcZuqr6_AD__xUUC_EN"

  def __init__(self):
    self.config = load_config()
    self.users_data = load_users_data()
    self._metadata_cache: Dict[str, Optional[str]] = {}

  def reload_config(self):
    self.config = load_config()
    self.users_data = load_users_data()

  def _resolve_series_title(self, content_id: str) -> Optional[str]:
    if content_id in self._metadata_cache:
      return self._metadata_cache[content_id]

    url = None
    if content_id.startswith("tt") and content_id[2:].isdigit():
      url = f"https://v3-cinemeta.strem.io/meta/series/{content_id}.json"
    elif content_id.startswith("kitsu:") and content_id[6:].isdigit():
      url = f"https://kitsu.io/api/edge/anime/{content_id[6:]}"

    if not url:
      self._metadata_cache[content_id] = None
      return None

    try:
      response = requests.get(url, timeout=5)
      response.raise_for_status()
      data = response.json()
      if content_id.startswith("kitsu:"):
        attributes = data.get("data", {}).get("attributes", {})
        titles = attributes.get("titles", {})
        title = titles.get("en") or attributes.get("canonicalTitle") or titles.get("en_jp")
      else:
        title = data.get("meta", {}).get("name")
    except requests.RequestException as e:
      print(f"[Nuvio Metadata] Errore recupero titolo per {content_id}: {e}")
      return None
    except (ValueError, AttributeError, TypeError) as e:
      print(f"[Nuvio Metadata] Risposta non valida per {content_id}: {e}")
      return None

    self._metadata_cache[content_id] = title
    return title

  def get_nuvio_access_token(self, email: str, password: str) -> str:
    if not email or not password:
      print("[Nuvio Auth] Email o password non configurati.")
      return ""

    url = "https://api.nuvio.tv/auth/v1/token?grant_type=password"
    headers = {
        "Content-Type": "application/json",
        "apikey": self.NUVIO_PUBLISHABLE_KEY,
    }
    payload = {"email": email, "password": password}

    try:
      response = requests.post(url, json=payload, headers=headers, timeout=10)
      if response.status_code == 200:
        return response.json().get("access_token", "")
    except Exception as e:
      print(f"[Nuvio Auth] Eccezione durante il login: {e}")
    return ""

  def get_nuvio_profiles(self, access_token: Optional[str] = None) -> List[Dict[str, Any]]:
    self.reload_config()
    nuvio_cfg = self.config.get("nuvio", {})
    token = access_token or self.get_nuvio_access_token(
        nuvio_cfg.get("email", ""), nuvio_cfg.get("password", "")
    )
    
    if not token:
      return [{"id": 1, "name": "Profilo Principale"}]

    url = "https://api.nuvio.tv/rest/v1/rpc/sync_pull_profiles"
    headers = {
        "Content-Type": "application/json",
        "apikey": self.NUVIO_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {token}",
    }

    try:
      response = requests.post(url, headers=headers, timeout=10)
      if response.status_code == 200:
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
          return [{"id": p.get("profile_index", 1), "name": p.get("name", f"Profilo {p.get('profile_index', 1)}") } for p in data]
    except Exception as e:
      print(f"[Nuvio Profiles] Eccezione: {e}")

    return [{"id": 1, "name": "Profilo Principale"}]

  def get_nuvio_library(self) -> List[Dict[str, Any]]:
    self.reload_config()
    nuvio_cfg = self.config.get("nuvio", {})
    profile_id = int(self.users_data.get("active_profile_id", 1) or 1)

    token = self.get_nuvio_access_token(nuvio_cfg.get("email", ""), nuvio_cfg.get("password", ""))
    if not token:
      return []

    url = "https://api.nuvio.tv/rest/v1/rpc/sync_pull_library"
    headers = {
        "Content-Type": "application/json",
        "apikey": self.NUVIO_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {token}",
    }
    payload = {"p_profile_id": profile_id, "p_limit": 500, "p_offset": 0}

    items_list = []
    try:
      response = requests.post(url, json=payload, headers=headers, timeout=10)
      if response.status_code == 200:
        for item in response.json() if isinstance(response.json(), list) else []:
          title = item.get("name", item.get("title", ""))
          if title:
            items_list.append({
                "content_id": item.get("content_id", title),
                "title": title,
                "type": item.get("content_type", "show"),
                "poster": item.get("poster", ""),
                "source": "Nuvio",
            })
    except Exception as e:
      print(f"[Nuvio Library] Eccezione: {e}")

    return items_list

  def get_nuvio_addons(self) -> List[Dict[str, Any]]:
    self.reload_config()
    nuvio_cfg = self.config.get("nuvio", {})
    token = self.get_nuvio_access_token(nuvio_cfg.get("email", ""), nuvio_cfg.get("password", ""))
    if not token:
      raise ValueError("Credenziali Nuvio mancanti o non valide.")

    profile_id = int(self.users_data.get("active_profile_id", 1) or 1)
    try:
      response = requests.get(
          "https://api.nuvio.tv/rest/v1/addons",
          params={
              "select": "url,name,enabled,sort_order,profile_id",
              "profile_id": f"eq.{profile_id}",
              "enabled": "eq.true",
              "order": "sort_order.asc",
          },
          headers={
              "apikey": self.NUVIO_PUBLISHABLE_KEY,
              "Authorization": f"Bearer {token}",
          },
          timeout=10,
      )
      response.raise_for_status()
      data = response.json()
      if not isinstance(data, list):
        raise ValueError("Risposta addon Nuvio non valida.")

      addons = []
      for item in data:
        url = item.get("url")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
          continue
        hostname = urlsplit(url).hostname or url
        addons.append({
            "url": url,
            "name": item.get("name") or hostname,
            "enabled": bool(item.get("enabled", True)),
            "sort_order": item.get("sort_order", 0),
        })
      return addons
    except (requests.RequestException, ValueError) as e:
      print(f"[Nuvio Addons] Errore recupero addon: {e}")
      raise RuntimeError("Impossibile recuperare gli addon installati su Nuvio.") from e

  @staticmethod
  def _addon_stream_url(addon_url: str, media_type: str, video_id: str) -> str:
    parsed = urlsplit(addon_url)
    path = parsed.path.rstrip("/")
    if path.endswith("/manifest.json"):
      path = path[:-len("/manifest.json")]
    elif path == "manifest.json":
      path = ""
    return parsed._replace(
        path=f"{path}/stream/{media_type}/{quote(video_id, safe='')}.json",
        fragment="",
    ).geturl()

  @staticmethod
  def _stream_matches_language(stream: Dict[str, Any], language: str) -> bool:
    language = language.strip().lower()
    if language in {"ita", "it", "italian", "italiano"}:
      pattern = re.compile(r"(?<![a-z])(?:ita|italian|italiano)(?![a-z])", re.IGNORECASE)
      flag = "🇮🇹"
    elif language in {"eng", "en", "english"}:
      pattern = re.compile(r"(?<![a-z])(?:eng|english)(?![a-z])", re.IGNORECASE)
      flag = "🇬🇧"
    else:
      if not language:
        return False
      pattern = re.compile(
          rf"(?<![a-z]){re.escape(language)}(?![a-z])",
          re.IGNORECASE,
      )
      flag = ""

    fields = (
        "name", "title", "description", "language", "languages",
        "audio", "audioTracks", "audio_tracks",
    )
    values = [str(stream[field]) for field in fields if stream.get(field) is not None]
    return flag in values or any(pattern.search(value) for value in values)

  def _find_language_stream(
      self,
      addons: List[Dict[str, Any]],
      media_type: str,
      video_id: str,
      language: str,
      ui_logs: List[str],
  ) -> bool:
    for addon in addons:
      addon_name = addon.get("name") or urlsplit(addon["url"]).hostname or "Addon"
      url = self._addon_stream_url(addon["url"], media_type, video_id)
      try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("streams"), list):
          ui_logs.append(f"  ⚠ {addon_name}: risposta senza un elenco di flussi valido.")
          continue
        streams = payload["streams"]
        if any(
            isinstance(stream, dict) and self._stream_matches_language(stream, language)
            for stream in streams
        ):
          ui_logs.append(f"  ✔ {addon_name}: flusso {language.upper()} trovato.")
          return True
      except requests.RequestException as e:
        ui_logs.append(f"  ⚠ {addon_name}: richiesta non riuscita ({e}).")
      except (ValueError, TypeError, AttributeError) as e:
        ui_logs.append(f"  ⚠ {addon_name}: risposta non valida ({e}).")
    return False

  def get_nuvio_history(self) -> List[Dict[str, Any]]:
    self.reload_config()
    nuvio_cfg = self.config.get("nuvio", {})
    profile_id = int(self.users_data.get("active_profile_id", 1) or 1)
    
    token = self.get_nuvio_access_token(nuvio_cfg.get("email", ""), nuvio_cfg.get("password", ""))
    if not token:
      return []

    latest_progress: Dict[str, Dict[str, Any]] = {}
    title_lookup = {item["content_id"]: item["title"] for item in self.get_nuvio_library()}
    notification_prefs = self.users_data.get("notification_prefs", {})
    headers = {
        "Content-Type": "application/json",
        "apikey": self.NUVIO_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {token}",
    }

    # Watch Progress
    try:
      resp = requests.post("https://api.nuvio.tv/rest/v1/rpc/sync_pull_watch_progress", json={"p_profile_id": profile_id, "p_limit": 200}, headers=headers, timeout=10)
      if resp.status_code == 200 and isinstance(resp.json(), list):
        for item in resp.json():
          if str(item.get("content_type", "series")).lower() in {"movie", "film"}:
            continue
          cid = item.get("content_id")
          if not cid:
            continue
          cid = str(cid)
          try:
            watched_at = int(item.get("last_watched", 0) or 0)
          except (TypeError, ValueError):
            watched_at = 0
          previous_progress = latest_progress.get(cid)
          if previous_progress and previous_progress["last_watched"] >= watched_at:
            continue

          latest_progress[cid] = {
              **item,
              "last_watched": watched_at,
          }
    except Exception as e:
      print(f"[Watch Progress] {e}")

    history_map = {}
    for cid, item in latest_progress.items():
      title = title_lookup.get(cid) or item.get("title", "")
      if (
        not title
        or title == cid
        or title.startswith(("tmdb:", "kitsu:"))
        or (title.startswith("tt") and title[2:].isdigit())
      ):
        title = self._resolve_series_title(cid)
      if not title:
        title = f"Titolo non disponibile ({cid})"

      history_map[cid] = {
          "content_id": cid,
          "title": title,
          "type": item.get("content_type", "series"),
          "season": item.get("season"),
          "episode": item.get("episode"),
          "watched_at": item["last_watched"],
          "notifications_enabled": notification_prefs.get(cid, True),
          "source": "Nuvio",
      }

    history_list = list(history_map.values())
    history_list.sort(key=lambda x: x.get("watched_at", 0), reverse=True)
    return history_list

  def get_unified_library(self) -> List[Dict[str, Any]]:
    self.reload_config()
    library = []
    seen = set()
    notification_prefs = self.users_data.get("notification_prefs", {})

    for item in self.get_nuvio_library():
      cid = item["content_id"]
      if cid not in seen:
        seen.add(cid)
        library.append({**item, "notifications_enabled": notification_prefs.get(cid, True)})

    for item in self.config.get("manual_shows", []):
      title = item.get("title")
      if title:
        cid = f"manual:{title.lower()}"
        if cid not in seen:
          seen.add(cid)
          library.append({
              "content_id": cid,
              "title": title,
              "type": item.get("type", "show"),
              "notifications_enabled": notification_prefs.get(cid, True),
              "source": "Manuale",
          })

    library.sort(key=lambda x: x["title"].lower())
    return library

  def toggle_all_notifications(self, enabled: bool, scope: str) -> None:
    self.reload_config()
    notification_prefs = self.users_data.get("notification_prefs", {})
    if scope == "library":
      items = self.get_unified_library()
    elif scope == "history":
      items = self.get_nuvio_history()
    else:
      raise ValueError("Scheda notifiche non valida.")

    for item in items:
      if cid := item.get("content_id"):
        notification_prefs[cid] = enabled
    self.users_data["notification_prefs"] = notification_prefs
    save_users_data(self.users_data)

  @staticmethod
  def merge_notification_targets(
      library_items: List[Dict[str, Any]],
      history_items: List[Dict[str, Any]],
  ) -> List[Dict[str, Any]]:
    targets: Dict[str, Dict[str, Any]] = {}
    for item in library_items:
      if item.get("source") == "Manuale":
        continue
      content_id = str(item.get("content_id") or "")
      if content_id:
        targets[content_id] = {**item, "content_id": content_id}

    for item in history_items:
      content_id = str(item.get("content_id") or "")
      if not content_id:
        continue
      library_item = targets.get(content_id, {})
      targets[content_id] = {
          **library_item,
          **item,
          "content_id": content_id,
          "notifications_enabled": item.get(
              "notifications_enabled",
              library_item.get("notifications_enabled", True),
          ),
      }

    return list(targets.values())

  def check_for_releases(self) -> Dict[str, Any]:
    self.reload_config()
    dub_lang = self.config.get("dubbing_language", "ita")
    telegram_cfg = self.config.get("telegram", {})
    profile_id = str(self.users_data.get("active_profile_id", 1))
    bot_token = telegram_cfg.get("bot_token", "")
    profiles_telegram = self.users_data.get("profiles_telegram", {})
    inherit_prefs = self.users_data.get("inherit_main_telegram", {})
    use_main_telegram = profile_id != "1" and inherit_prefs.get(profile_id, True)
    if profile_id == "1" or use_main_telegram:
      chat_id = profiles_telegram.get("1") or telegram_cfg.get("chat_id", "")
    else:
      chat_id = profiles_telegram.get(profile_id, "")

    notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id)
    found_releases = []
    ui_logs = [f"Avvio controllo uscite (Profilo ID {profile_id}, Lingua: {dub_lang.upper()})..."]
    if not notifier.is_configured():
      ui_logs.append("Telegram non configurato: le uscite verranno controllate ma non potranno essere notificate.")

    try:
      available_addons = self.get_nuvio_addons()
    except (ValueError, RuntimeError) as e:
      ui_logs.append(f"Controllo interrotto: {e}")
      return {"found": found_releases, "logs": ui_logs}

    selected_by_profile = self.users_data.get("selected_addons", {})
    selected_urls = selected_by_profile.get(profile_id)
    if selected_urls is None:
      selected_urls = [addon["url"] for addon in available_addons]
    selected_urls = set(selected_urls)
    addons = [addon for addon in available_addons if addon["url"] in selected_urls]
    if not addons:
      ui_logs.append("Nessun addon selezionato per questo profilo. Seleziona almeno un addon nelle impostazioni.")
      return {"found": found_releases, "logs": ui_logs}

    ui_logs.append(f"Addon interrogati: {', '.join(addon['name'] for addon in addons)}.")
    history_items = self.get_nuvio_history()
    library_items = self.get_unified_library()
    notification_targets = self.merge_notification_targets(library_items, history_items)
    history_by_id = {
        str(item["content_id"]): item
        for item in history_items
        if item.get("content_id")
    }
    notified = self.users_data.setdefault("notified_releases", {})

    for item in notification_targets:
      if not item.get("notifications_enabled", True):
        continue

      title = item.get("title", "")
      content_id = str(item.get("content_id") or "")
      if not content_id:
        continue
      is_movie = str(item.get("type", "series")).lower() in {"movie", "film"}
      if is_movie:
        media_type = "movie"
        season = episode = None
        video_id = content_id
        release_key = f"{profile_id}:{content_id}:movie"
      else:
        media_type = "series"
        watched_info = history_by_id.get(content_id, {})
        try:
          season = int(watched_info.get("season") or 1)
        except (TypeError, ValueError):
          season = 1
        try:
          watched_episode = int(watched_info.get("episode") or 0)
        except (TypeError, ValueError):
          watched_episode = 0
        episode = watched_episode + 1
        video_id = f"{content_id}:{season}:{episode}"
        release_key = f"{profile_id}:{content_id}:S{season}E{episode}"

      if notified.get(release_key):
        ui_logs.append(f"• {title}: notifica già inviata.")
        continue

      ui_logs.append(
          f"Controllo {title}"
          + (f" (S{season:02d}E{episode:02d})..." if not is_movie else " (film)...")
      )

      is_released = self._find_language_stream(
          addons=addons,
          media_type=media_type,
          video_id=video_id,
          language=dub_lang,
          ui_logs=ui_logs,
      )
      if is_released:
        release: Dict[str, Any] = {"title": title, "type": media_type}
        if not is_movie:
          release.update({"season": season, "episode": episode})
        found_releases.append(release)

        sent = notifier.is_configured() and notifier.send_release_notification(
            title=title,
            media_type=media_type,
            season=season or 0,
            episode=episode or 0,
            ep_title=f"Stagione {season} Episodio {episode}" if not is_movie else title,
            dub_lang=dub_lang,
        )
        if sent:
          notified[release_key] = True
          save_users_data(self.users_data)
          ui_logs.append(f"✔ Notifica Telegram inviata: {title}.")
        else:
          ui_logs.append(f"⚠ Flusso trovato per {title}, ma la notifica Telegram non è stata inviata.")
      else:
        ui_logs.append(
            f"• {title}: nessun flusso {dub_lang.upper()} trovato"
            + (f" per S{season:02d}E{episode:02d}." if not is_movie else ".")
        )

    ui_logs.append(f"Controllo terminato. Trovate {len(found_releases)} nuove uscite.")
    return {"found": found_releases, "logs": ui_logs}