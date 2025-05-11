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
    def __init__(self, memory_storage=None):
        self.ai_service = AIService(StrategyRegistry.get_strategy("deepseek"))
        self.text_processor = TextProcessor()
        self.memory_storage = memory_storage

    async def handle_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id if update.effective_chat else None
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
        prompt = self._create_qa_prompt(original_messages, question)
        answer = self.ai_service.get_response(prompt)

        if answer is None:
            logger.error("Failed to get response from AI service")
            answer = "Sorry, I couldn't find an answer for this question."

        formatted_answer = self.text_processor.escape_markdown(answer)
        if update.effective_chat is None:
            logger.error("Effective Chat is None")
            return

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=formatted_answer,
            parse_mode="MarkdownV2",
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
