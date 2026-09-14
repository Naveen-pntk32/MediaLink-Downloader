import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file in the project root
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE)
else:
    load_dotenv()

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# Local PC Download Directory
_default_download = r"C:\Downloads" if os.name == "nt" else str(Path.home() / "Downloads")
PC_DOWNLOAD_DIR = os.getenv("PC_DOWNLOAD_DIR", _default_download).strip()
os.makedirs(PC_DOWNLOAD_DIR, exist_ok=True)

# Temp Download Directory for Telegram Chat uploads
TEMP_DOWNLOAD_DIR = BASE_DIR / "downloads" / "temp"
os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)

# Allowed Telegram User IDs (Optional whitelist)
_allowed_raw = os.getenv("ALLOWED_USER_IDS", "").strip()
if _allowed_raw:
    ALLOWED_USER_IDS = set()
    for uid in _allowed_raw.split(","):
        uid_clean = uid.strip()
        if uid_clean.isdigit():
            ALLOWED_USER_IDS.add(int(uid_clean))
else:
    ALLOWED_USER_IDS = None

# Cookies File for Instagram & YouTube Authentication
_cookie_env = os.getenv("COOKIES_FILE", "cookies.txt").strip()
COOKIES_FILE_PATH = Path(_cookie_env)
if not COOKIES_FILE_PATH.is_absolute():
    COOKIES_FILE_PATH = BASE_DIR / _cookie_env


# Support passing cookies directly via environment variable (useful on Render / Docker)
_cookies_content = os.getenv("COOKIES_CONTENT", "").strip()
if _cookies_content and (not COOKIES_FILE_PATH.exists() or COOKIES_FILE_PATH.stat().st_size == 0):
    try:
        with open(COOKIES_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(_cookies_content)
    except Exception as e:
        pass


def has_valid_cookies() -> bool:
    """Return True if cookies.txt exists and is non-empty."""
    return COOKIES_FILE_PATH.exists() and COOKIES_FILE_PATH.stat().st_size > 0
