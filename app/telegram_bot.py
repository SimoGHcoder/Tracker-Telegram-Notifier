import requests
import logging
from html import escape

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, bot_token: str = "", token: str = "", chat_id: str = ""):
        self.bot_token = bot_token or token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else ""

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_message(self, chat_id: str, text: str) -> bool:
        """Invia un messaggio HTML ad un determinato chat_id."""
        target_chat = chat_id or self.chat_id
        if not target_chat or not self.base_url:
            return False
            
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": text,
            "parse_mode": "HTML"
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Errore invio messaggio Telegram: {e}")
            return False

    def send_release_notification(self, title: str, media_type: str, season: int, episode: int, ep_title: str, dub_lang: str) -> bool:
        """Invia la notifica di un nuovo episodio o film rilasciato."""
        safe_title = escape(title)
        safe_language = escape(dub_lang.upper())
        if media_type.lower() in {"movie", "film"}:
            text = (
                "🎬 <b>Nuovo film disponibile!</b>\n\n"
                f"<b>{safe_title}</b>\n"
                f"Lingua: <b>{safe_language}</b>"
            )
        else:
            episode_label = ep_title or f"Stagione {season}, Episodio {episode}"
            text = (
                f"🎬 <b>Nuovo Episodio Disponibile!</b>\n\n"
                f"<b>{safe_title}</b>\n"
                f"{escape(episode_label)}\n"
                f"Lingua: <b>{safe_language}</b>"
            )
        return self.send_message(self.chat_id, text)

    def get_updates(self, offset=None):
        """Recupera gli ultimi messaggi inviati al bot."""
        if not self.base_url:
            return []
        url = f"{self.base_url}/getUpdates"
        params = {"timeout": 5, "offset": offset}
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("result", [])
        except Exception as e:
            logger.error(f"Errore getUpdates Telegram: {e}")
        return []

    def get_bot_username(self) -> str:
        """Restituisce lo username del bot interrogando le API di Telegram."""
        if not self.base_url:
            return None
        url = f"{self.base_url}/getMe"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data["result"].get("username")
        except Exception as e:
            logger.error(f"Errore get_bot_username: {e}")
        return None

    def resolve_start_code_with_user(self, code: str):
        """Cerca nei messaggi recenti il comando /start con il codice e restituisce (chat_id, user_display_name)"""
        updates = self.get_updates()
        for update in updates:
            message = update.get("message")
            if message:
                text = message.get("text", "")
                if text == f"/start {code}" or text.startswith(f"/start {code}"):
                    chat = message.get("chat", {})
                    user = message.get("from", {})
                    chat_id = str(chat.get("id"))
                    
                    username = user.get("username")
                    first_name = user.get("first_name", "")
                    last_name = user.get("last_name", "")
                    
                    if username:
                        display_name = f"@{username}"
                    elif first_name or last_name:
                        display_name = f"{first_name} {last_name}".strip()
                    else:
                        display_name = f"Utente {chat_id}"
                        
                    return chat_id, display_name
        return None, None

    def verify_credentials(self) -> dict:
        """Verifica se il Bot Token è valido e restituisce le info sul Bot."""
        username = self.get_bot_username()
        return {"valid": bool(username), "username": username}