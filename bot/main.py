#!/usr/bin/env python3
"""
TLDRBot - A witty Telegram bot for group chat summarization.
"""
import logging
from telegram.ext import MessageHandler, filters

import config
from core import TLDRBot, AIService, RateLimiter
from plugins import HelpPlugin, SummarizePlugin, MentionReplyPlugin, AutoDownloadPlugin
from storage import MemoryStorage

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    config.validate_config()
    
    if config.DATABASE_URL:
        from storage.analytics import init_database, create_tables
        if init_database(config.DATABASE_URL):
            create_tables()
    
    ai_service = AIService(config.OPENAI_API_KEY, config.AI_MODEL)
    rate_limiter = RateLimiter(max_uses_per_day=config.DAILY_LIMIT)
    memory = MemoryStorage(max_messages=config.MAX_MESSAGES)
    
    bot = TLDRBot(config.BOT_TOKEN or "")
    bot.register_plugin(HelpPlugin())
    bot.register_plugin(SummarizePlugin(ai_service, rate_limiter, memory))
    bot.register_plugin(MentionReplyPlugin(ai_service, rate_limiter, memory))
    bot.register_plugin(AutoDownloadPlugin())
    
    app = bot.setup()
    
    async def store_message(update, context):
        if update.message and update.message.text and update.effective_chat and update.effective_user:
            if update.message.text.startswith('/'):
                return
            sender_name = update.effective_user.first_name or update.effective_user.username or "Someone"
            memory.store_message(update.effective_chat.id, sender_name, update.message.text)
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, store_message), group=99)
    
    logger.info("🤖 TLDRBot starting up...")
    
    if config.WEBHOOK_URL:
        bot.run_webhook("0.0.0.0", config.PORT, config.BOT_TOKEN or "", f"{config.WEBHOOK_URL}{config.BOT_TOKEN}")
    else:
        bot.run_polling()


if __name__ == "__main__":
    main()
