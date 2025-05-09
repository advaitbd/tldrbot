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
from services.redis_queue import RedisQueue
import re
from utils.analytics_storage import create_tables  # <-- NEW
import json

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
        self.redis_queue = RedisQueue()
        self.command_handlers = CommandHandlers(self.memory_storage, redis_queue=self.redis_queue)
        self._worker_task = None

    def setup(self):
        if not TelegramConfig.BOT_TOKEN:
            raise ValueError("BOT_TOKEN environment variable is not set")

        application = ApplicationBuilder().token(TelegramConfig.BOT_TOKEN).build()

        # Register handlers
        self._register_handlers(application)

        # Register post-init callback to set up commands
        application.post_init = self._setup_commands

        # Start background worker for LLM jobs
        loop = asyncio.get_event_loop()
        if not self._worker_task:
            self._worker_task = loop.create_task(self._llm_worker(application))

        return application

    def _register_handlers(self, application):
            # Command handlers
            application.add_handler(CommandHandler("help", self.command_handlers.help_command))
            application.add_handler(CommandHandler("tldr", self.command_handlers.summarize))
            application.add_handler(CommandHandler("dl", self.telegram_service.download_tiktok))
            application.add_handler(CommandHandler("switch_model", self.command_handlers.switch_model))
            application.add_handler(CommandHandler("set_api_key", self.command_handlers.set_api_key))
            application.add_handler(CommandHandler("clear_api_key", self.command_handlers.clear_api_key))
            application.add_handler(CommandHandler("list_providers", self.command_handlers.list_providers))
            # Bill splitting conversation (receipt + confirmation)
            split_conv = ConversationHandler(
                entry_points=[CommandHandler("splitbill", self.command_handlers.split_bill_start)],
                states={
                    RECEIPT_IMAGE: [MessageHandler(filters.PHOTO & filters.Caption(),
                                                   self.command_handlers.split_bill_photo_with_context)],
                    CONFIRMATION: [
                        MessageHandler(filters.Regex("(?i)^(confirm|✅)$"),
                                       self.command_handlers.split_bill_confirm),
                        MessageHandler(filters.Regex("(?i)^(cancel|no)$"),
                                       self.command_handlers.split_bill_cancel),
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.command_handlers.split_bill_cancel)],
                per_user=True,
                per_chat=True,
            )
            application.add_handler(split_conv)
            # Message handlers
            # Only add if reply_handler exists (diagnostic fix)
            if hasattr(self.message_handlers, "handle_reply") and callable(getattr(self.message_handlers, "handle_reply", None)):
                application.add_handler(MessageHandler(
                    filters.REPLY & ~filters.COMMAND,  # Ensure it's not a command reply
                    self.message_handlers.handle_reply
                ))

            # Inline query handler
            application.add_handler(InlineQueryHandler(self.command_handlers.inline_query))

            # Message storage handler (ensure it doesn't interfere with conversation text)
            # We only want to store general chat messages, not context replies in the conversation
            application.add_handler(MessageHandler(
                filters.TEXT & ~filters.COMMAND & (~filters.UpdateType.EDITED_MESSAGE),  # Added filter for edited msg
                self._store_in_memory), group=1)  # Use a group to ensure it runs after conv handler maybe? Or rely on conv handler stopping propagation.


    async def _setup_commands(self, application):
        """Set up the bot commands that appear in the bot menu"""
        commands = [
            BotCommand("help", "Show help information"),
            BotCommand("tldr", "Summarize recent messages"),
            BotCommand("splitbill", "Split bill from receipt"),
            BotCommand("dl", "Download TikTok videos"),
            BotCommand("switch_model", "Switch AI model (QA/Summary)"),
            BotCommand("set_api_key", "Set your own API key for a provider"),
            BotCommand("clear_api_key", "Remove your API key for a provider"),
            BotCommand("list_providers", "List all valid provider names"),
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
                    # Check conversation state using context.user_data
                    user_state = context.user_data.get('conversation_state')
                    if user_state and user_state != ConversationHandler.END:
                        logger.debug(f"Message from user {update.effective_user.id} ignored by storage (in conversation state {user_state}).")
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

    async def _llm_worker(self, application):
        """Background worker to process LLM jobs from Redis queue."""
        from telegram.constants import ParseMode
        while True:
            job = await self.redis_queue.dequeue(timeout=5)
            if not job:
                await asyncio.sleep(1)
                continue
            if job.get("type") == "tldr":
                chat_id = job["chat_id"]
                prompt = job["prompt"]
                num_messages = job.get("num_messages", 50)
                user_name = job.get("user_id", "User")
                original_messages = job.get("original_messages", [])
                try:
                    # Always use the latest ai_service (strategy may change per user)
                    response = self.command_handlers.ai_service.get_response(prompt)
                    formatted_summary = self.command_handlers._format_summary(str(response), user_name, num_messages)
                    await application.bot.send_message(
                        chat_id=chat_id,
                        text=formatted_summary,
                        parse_mode=ParseMode.MARKDOWN_V2,
                        disable_web_page_preview=True,
                    )
                except Exception as e:
                    logger.error(f"LLM worker error: {e}")
                    await application.bot.send_message(
                        chat_id=chat_id,
                        text="Sorry, I couldn't generate a summary due to an error.",
                        disable_web_page_preview=True,
                    )

def main():
    # Ensure analytics table exists before starting the bot
    create_tables()
    bot = Bot()
    application = bot.setup()

    if TelegramConfig.WEBHOOK_URL:
        # Ensure BOT_TOKEN is a string (not None) for url_path
        url_path = TelegramConfig.BOT_TOKEN if TelegramConfig.BOT_TOKEN is not None else ""
        application.run_webhook(
            listen="0.0.0.0",
            port=TelegramConfig.PORT,
            url_path=url_path,
            webhook_url=f"{TelegramConfig.WEBHOOK_URL}{url_path}",
        )
        logger.info("Application running via webhook")
    else:
        application.run_polling()
        logger.info("Application running via polling")

if __name__ == "__main__":
    main()
