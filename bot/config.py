"""Configuration for TLDRBot."""
import os
import json

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

_DEFAULT_VIDEO_URL_PATTERNS = [
    r'https?://(www\.)?tiktok\.com/',
    r'https?://(www\.)?vt.tiktok\.com/', 
    r'https?://vm\.tiktok\.com/',
    r'https?://(www\.)?instagram\.com/reel/',
    r'https?://(www\.)?youtube\.com/shorts/',
    r'https?://youtu\.be/',
]

_video_patterns_env = os.environ.get("VIDEO_URL_PATTERNS")
if _video_patterns_env:
    try:
        VIDEO_URL_PATTERNS = json.loads(_video_patterns_env)
        if not isinstance(VIDEO_URL_PATTERNS, list):
            raise ValueError("VIDEO_URL_PATTERNS must be a JSON array")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in VIDEO_URL_PATTERNS environment variable: {e}")
else:
    VIDEO_URL_PATTERNS = _DEFAULT_VIDEO_URL_PATTERNS

