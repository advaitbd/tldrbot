import logging
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    InlineQueryHandler,
    filters,
)
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
        self.command_handlers = CommandHandlers()
        self.message_handlers = MessageHandlers()
        self.telegram_service = TelegramService()

    def setup(self):
        if not TelegramConfig.BOT_TOKEN:
            raise ValueError("BOT_TOKEN environment variable is not set")

        application = ApplicationBuilder().token(TelegramConfig.BOT_TOKEN).build()

        # Register handlers
        self._register_handlers(application)

        return application

    def _register_handlers(self, application):
        # Command handlers
        application.add_handler(CommandHandler("start", self.command_handlers.start))
        application.add_handler(CommandHandler("help", self.command_handlers.help_command))
        application.add_handler(CommandHandler("tldr", self.command_handlers.summarize))
        application.add_handler(CommandHandler("dl", self.telegram_service.download_tiktok))

        # Message handlers
        application.add_handler(MessageHandler(
            filters.REPLY, 
            self.message_handlers.handle_reply
        ))

        # Inline query handler
        application.add_handler(InlineQueryHandler(self.command_handlers.inline_query))

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