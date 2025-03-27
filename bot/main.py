# TeleBot/bot/main.py
import logging
import asyncio
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    InlineQueryHandler,
    filters,
)
from telegram import BotCommand
from utils.memory_storage import MemoryStorage
from config.settings import TelegramConfig
from handlers.command_handlers import CommandHandlers
from handlers.message_handlers import MessageHandlers
from services.telegram_service import TelegramService

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class Bot:
    def __init__(self):
        self.message_handlers = MessageHandlers()
        self.telegram_service = TelegramService()
        self.memory_storage = MemoryStorage(max_messages=400)
        self.command_handlers = CommandHandlers(self.memory_storage)

    def setup(self):
        if not TelegramConfig.BOT_TOKEN:
            raise ValueError("BOT_TOKEN environment variable is not set")

        application = ApplicationBuilder().token(TelegramConfig.BOT_TOKEN).build()

        # Register handlers
        self._register_handlers(application)

        # Register post-init callback to set up commands
        application.post_init = self._setup_commands

        return application

    def _register_handlers(self, application):
        # Command handlers
        application.add_handler(CommandHandler("help", self.command_handlers.help_command))
        application.add_handler(CommandHandler("tldr", self.command_handlers.summarize))
        application.add_handler(CommandHandler("dl", self.telegram_service.download_tiktok))
        application.add_handler(CommandHandler("switch_model", self.command_handlers.switch_model))

        # Message handlers
        application.add_handler(MessageHandler(
            filters.REPLY,
            self.message_handlers.handle_reply
        ))

        # Inline query handler
        application.add_handler(InlineQueryHandler(self.command_handlers.inline_query))

        # Message storage handler
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._store_in_memory))

    async def _setup_commands(self, application):
        """Set up the bot commands that appear in the bot menu"""
        commands = [
            BotCommand("help", "Show help information"),
            BotCommand("tldr", "Summarize recent messages"),
            BotCommand("dl", "Download TikTok videos"),
            BotCommand("switch_model", "Switch AI model")
        ]

        await application.bot.set_my_commands(commands)

    async def _store_in_memory(self, update, context):
        """
        Handler to store messages in-memory
        """
        chat_id = update.effective_chat.id
        sender_name = update.effective_user.name if update.effective_user else "Unknown"
        message = update.message.text
        self.memory_storage.store_message(chat_id, sender_name, message)

def main():
    bot = Bot()
    application = bot.setup()

    if TelegramConfig.WEBHOOK_URL:
        application.run_webhook(
            listen="0.0.0.0",
            port=TelegramConfig.PORT,
            url_path=TelegramConfig.BOT_TOKEN,
            webhook_url=f"{TelegramConfig.WEBHOOK_URL}{TelegramConfig.BOT_TOKEN}",
        )
        logger.info("Application running via webhook")
    else:
        application.run_polling()
        logger.info("Application running via polling")

if __name__ == "__main__":
    main()
