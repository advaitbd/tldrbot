"""
Configuration classes for environment variables.
"""
import os

# Check if all required environment variables are set
required_vars = ["BOT_TOKEN", "OPENAI_API_KEY"]
missing_vars = [var for var in required_vars if os.environ.get(var) is None]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")


class TelegramConfig:
    """Telegram bot configuration."""
    BOT_TOKEN: str | None = os.environ.get("BOT_TOKEN")
    PORT: int = int(os.environ.get("PORT", "5000"))
    WEBHOOK_URL: str | None = os.environ.get("WEBHOOK_URL")


class OpenAIConfig:
    """OpenAI API configuration."""
    API_KEY: str | None = os.environ.get("OPENAI_API_KEY")
    MINI_MODEL: str = os.environ.get("OPENAI_MINI_MODEL", "gpt-4o-mini")
    O4_MODEL: str = os.environ.get("OPENAI_4O_MODEL", "gpt-4o")
    FOUR_ONE_MODEL: str = os.environ.get("OPENAI_41_MODEL", "gpt-4.1")


class GroqAIConfig:
    """Groq AI API configuration."""
    API_KEY: str | None = os.environ.get("GROQ_API_KEY")
    MODEL: str = os.environ.get("GROQ_MODEL", "llama3-8b-8192")


class DeepSeekAIConfig:
    """DeepSeek AI API configuration."""
    API_KEY: str | None = os.environ.get("DEEPSEEK_API_KEY")
    MODEL: str = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")


class CensorConfig:
    """Content filtering configuration."""
    WORDS: str = os.environ.get("CENSOR", "")


class DatabaseConfig:
    """Database configuration."""
    DATABASE_URL: str | None = os.environ.get("DATABASE_URL")


class RedisConfig:
    """Redis configuration."""
    URL: str = os.environ.get("REDIS_URL")
