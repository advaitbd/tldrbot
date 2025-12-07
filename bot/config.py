"""Configuration for TLDRBot."""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
AI_MODEL = os.environ.get("AI_MODEL", "gpt-4o-mini")
DATABASE_URL = os.environ.get("DATABASE_URL")
MAX_MESSAGES = int(os.environ.get("MAX_MESSAGES", "400"))
DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "10"))
PORT = int(os.environ.get("PORT", "5000"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

def validate_config():
    missing = [k for k in ["BOT_TOKEN", "OPENAI_API_KEY"] if not os.environ.get(k)]
    if missing:
        raise ValueError(f"Missing: {', '.join(missing)}")

VIDEO_URL_PATTERNS = [
    r'https?://(www\.)?tiktok\.com/',
    r'https?://(www\.)?vt.tiktok\.com/', 
    r'https?://vm\.tiktok\.com/',
    r'https?://(www\.)?instagram\.com/reel/',
    r'https?://(www\.)?youtube\.com/shorts/',
    r'https?://youtu\.be/',
]

