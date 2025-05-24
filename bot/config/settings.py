import os
from dataclasses import dataclass, field
# import dotenv
# dotenv.load_dotenv()

# Check if all required environment variables are set
required_vars = ["BOT_TOKEN", "OPENAI_API_KEY"]
missing_vars = [var for var in required_vars if os.environ.get(var) is None]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

@dataclass
class TelegramConfig:
    BOT_TOKEN: str | None = os.environ.get("BOT_TOKEN")
    PORT: int = int(os.environ.get("PORT", "5000"))
    WEBHOOK_URL: str | None = os.environ.get("WEBHOOK_URL")

@dataclass
class OpenAIConfig:
    API_KEY: str | None = os.environ.get("OPENAI_API_KEY")
    MODEL: str | None = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

@dataclass
class GroqAIConfig:
    API_KEY: str | None = os.environ.get("GROQ_API_KEY")
    MODEL: str = os.environ.get("GROQ_MODEL", "llama3-8b-8192")

@dataclass
class DeepSeekConfig:
    API_KEY: str | None = os.environ.get("DEEPSEEK_API_KEY")
    MODEL: str = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

@dataclass
class CensorConfig:
    WORDS: str = os.environ.get("CENSOR", "")

@dataclass
class DatabaseConfig:
    DATABASE_URL: str | None = os.environ.get("DATABASE_URL")

@dataclass
class RedisConfig:
    URL: str = os.environ.get("REDIS_URL")

@dataclass
class StripeConfig:
    PAYMENT_LINK: str | None = os.environ.get("STRIPE_PAYMENT_LINK")
    WEBHOOK_SECRET: str | None = os.environ.get("STRIPE_WEBHOOK_SECRET")
    API_KEY: str | None = os.environ.get("STRIPE_API_KEY")

@dataclass
class AppConfig:
    ENV: str = os.environ.get("ENV", "development")
