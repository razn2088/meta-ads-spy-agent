import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# LLM
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Scraper anti-ban delays (seconds)
DELAY_MIN = 10
DELAY_MAX = 30

# Scroll settings for Meta Ads Library
SCROLL_PAUSE = 2.5
MAX_SCROLLS = 15

# Proxy (optional)
PROXY_URL = os.getenv("PROXY_URL", "")

# WhatsApp
ADMIN_WHATSAPP_GROUP = os.getenv("ADMIN_WHATSAPP_GROUP", "Admin Alerts")
WHATSAPP_PROFILE_DIR = os.getenv("WHATSAPP_PROFILE_DIR", str(BASE_DIR / "data" / "whatsapp_profile"))

# Data paths
DATA_DIR = BASE_DIR / "data"
HISTORY_DIR = DATA_DIR / "history"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"

# Clients config
CLIENTS_CONFIG_PATH = BASE_DIR / "config" / "clients.json"
