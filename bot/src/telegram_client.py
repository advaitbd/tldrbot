from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from .config import TELEGRAM_API_ID, TELEGRAM_API_HASH, STRING

async def get_telegram_client():
    client = TelegramClient(StringSession(STRING), TELEGRAM_API_ID, TELEGRAM_API_HASH)
    await client.start()
    return client
