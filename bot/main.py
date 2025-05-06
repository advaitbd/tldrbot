# TeleBot/bot/main.py
import logging
import asyncio
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    InlineQueryHandler,
    ConversationHandler,
    filters,
)
from telegram import BotCommand
from utils.memory_storage import MemoryStorage
from config.settings import TelegramConfig
from handlers.command_handlers import CommandHandlers, RECEIPT_IMAGE, CONFIRMATION # Import states
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
        # Bill splitting conversation (receipt + confirmation)
        split_conv = ConversationHandler(
            entry_points=[CommandHandler("splitbill", self.command_handlers.split_bill_start)],
            states={
                RECEIPT_IMAGE: [MessageHandler(filters.PHOTO & filters.Caption(),
                                               self.command_handlers.split_bill_photo_with_context)],
                CONFIRMATION: [
                    MessageHandler(filters.Regex("^(confirm|✅)$", flags=re.IGNORECASE),
                                   self.command_handlers.split_bill_confirm),
                    MessageHandler(filters.Regex("^(cancel|no)$", flags=re.IGNORECASE),
                                   self.command_handlers.split_bill_cancel),
                ],
            },
            fallbacks=[CommandHandler("cancel", self.command_handlers.split_bill_cancel)],
            per_user=True,
            per_chat=True,
        )
        application.add_handler(split_conv)
        # Message handlers
        application.add_handler(MessageHandler(
            filters.REPLY & ~filters.COMMAND, # Ensure it's not a command reply
            self.message_handlers.handle_reply
        ))

        # Inline query handler
        application.add_handler(InlineQueryHandler(self.command_handlers.inline_query))

        # Message storage handler (ensure it doesn't interfere with conversation text)
        # We only want to store general chat messages, not context replies in the conversation
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & (~filters.UpdateType.EDITED_MESSAGE), # Added filter for edited msg
            self._store_in_memory), group=1) # Use a group to ensure it runs after conv handler maybe? Or rely on conv handler stopping propagation.


    async def _setup_commands(self, application):
        """Set up the bot commands that appear in the bot menu"""
        commands = [
            BotCommand("help", "Show help information"),
            BotCommand("tldr", "Summarize recent messages"),
            BotCommand("splitbill", "Split bill from receipt"),
            BotCommand("dl", "Download TikTok videos"),
            BotCommand("switch_model", "Switch AI model (QA/Summary)"),
            BotCommand("cancel", "Cancel current operation (like bill split)"),
        ]
        await application.bot.set_my_commands(commands)

    async def _store_in_memory(self, update, context):
        """
        Handler to store messages in-memory. Check if part of a conversation first.
        """
        # Check if a conversation is active for this user
        current_handlers = context.application.handlers.get(0) # Assuming ConversationHandler is in group 0
        if isinstance(current_handlers, list): # Check if handlers is a list
             for handler in current_handlers:
                if isinstance(handler, ConversationHandler):
                    current_state = await handler.handle_update(update, context.application, check_result=None, context=context) # check_result=None avoids executing the handler, just gets state
                    if current_state != ConversationHandler.END:
                          logger.debug(f"Message from user {update.effective_user.id} ignored by storage (in conversation state {current_state}).")
                          return # Don't store messages while in an active conversation

        # If not in a conversation, proceed to store
        chat_id = update.effective_chat.id
        sender_name = update.effective_user.name if update.effective_user else "Unknown"
        message_text = update.message.text # Use message_text for clarity

        # Basic check to avoid storing the context message itself if the conversation check fails
        if context.user_data and 'receipt_data' in context.user_data:
             if update.message.text.startswith("Alice:") or update.message.text.startswith("Shared:"): # Heuristic
                 logger.debug("Message looks like payment context, not storing in general memory.")
                 return

        if message_text: # Ensure message has text content
             self.memory_storage.store_message(chat_id, sender_name, message_text)
             logger.debug(f"Stored message from {sender_name} in chat {chat_id}")

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
