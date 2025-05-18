from telegram import Update
from telegram.ext import ContextTypes
from utils.text_processor import TextProcessor
import logging
from services.ai.ai_service import AIService
from services.ai import StrategyRegistry
from config.settings import OpenAIConfig
from typing import List

logger = logging.getLogger(__name__)

class MessageHandlers:
    def __init__(self, memory_storage=None, redis_queue=None):
        self.ai_service = AIService(StrategyRegistry.get_strategy("deepseek"))
        self.text_processor = TextProcessor()
        self.memory_storage = memory_storage
        self.redis_queue = redis_queue

    async def handle_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id if update.effective_chat else None
        user_id = update.effective_user.id if update.effective_user else None
        summary_context = None
        if self.memory_storage and chat_id is not None:
            summary_context = self.memory_storage.get_summary_context(chat_id)
        if not self._is_valid_reply(update, summary_context):
            return

        if update.message is None or update.message.text is None:
            logger.error("No message or message text found in update")
            return

        question = update.message.text
        original_messages = summary_context["original_messages"] if summary_context else []

        # Enqueue the reply job in Redis
        job_data = {
            "type": "reply_to_summary",
            "chat_id": chat_id,
            "user_id": user_id,
            "question": question,
            "original_messages": original_messages,
            "summary_context": summary_context,
        }
        if self.redis_queue:
            await self.redis_queue.enqueue(job_data)
            # Optionally, notify the user that their request is being processed
            await context.bot.send_message(
                chat_id=chat_id,
                text="Your question has been received and will be answered soon!",
                disable_web_page_preview=True,
            )
        else:
            logger.error("Redis queue is not configured.")
            await context.bot.send_message(
                chat_id=chat_id,
                text="Sorry, the system is not ready to process your request.",
                disable_web_page_preview=True,
            )

    @staticmethod
    def _is_valid_reply(update: Update, summary_context) -> bool:
        if update.message is None or update.message.reply_to_message is None:
            return False

        if not summary_context or "summary_message_id" not in summary_context:
            return False

        summary_message_id = summary_context["summary_message_id"]
        return update.message.reply_to_message.message_id == summary_message_id

    @staticmethod
    def _create_qa_prompt(messages: List[str], question: str) -> str:
        return "\n".join(messages) + "\n\nQuestion: " + question
