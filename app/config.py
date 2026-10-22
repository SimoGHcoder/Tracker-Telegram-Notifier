import json
import os

CONFIG_PATH = os.path.join("data", "config.json")
USERS_PATH = os.path.join("data", "users.json")
EXAMPLE_PATH = "config.example.json"

APP_VERSION = "0.3.0-alpha.1"

def load_config() -> dict:
  os.makedirs("data", exist_ok=True)
  if not os.path.exists(CONFIG_PATH) and os.path.exists(EXAMPLE_PATH):
    try:
      with open(EXAMPLE_PATH, "r", encoding="utf-8") as f:
        default_config = json.load(f)
      save_config(default_config)
    except Exception:
      pass
  
  try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
      return json.load(f)
  except Exception:
    return {}

def save_config(config_data: dict) -> None:
  os.makedirs("data", exist_ok=True)
  with open(CONFIG_PATH, "w", encoding="utf-8") as f:
    json.dump(config_data, f, indent=2, ensure_ascii=False)

def load_users_data() -> dict:
  os.makedirs("data", exist_ok=True)
  if not os.path.exists(USERS_PATH):
    default_users = {
      "active_profile_id": 1,
      "profiles_telegram": {},
      "notification_prefs": {}
    }
    save_users_data(default_users)
    return default_users
  
  try:
    with open(USERS_PATH, "r", encoding="utf-8") as f:
      return json.load(f)
  except Exception:
    return {}

def save_users_data(users_data: dict) -> None:
  os.makedirs("data", exist_ok=True)
  with open(USERS_PATH, "w", encoding="utf-8") as f:
    json.dump(users_data, f, indent=2, ensure_ascii=False)