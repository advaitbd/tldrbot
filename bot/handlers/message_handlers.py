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
    def __init__(self):
        self.ai_service = AIService(StrategyRegistry.get_strategy("openai"))
        self.text_processor = TextProcessor()

    async def handle_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_valid_reply(update, context):
            return

        question = update.message.text
        if context.chat_data is None:
            context.chat_data = {}
        original_messages = context.chat_data.get('original_messages', [])
        prompt = self._create_qa_prompt(original_messages, question)
        answer = self.ai_service.get_response(prompt)

        if answer is None:
            logger.error("Failed to get response from AI service")
            answer = "Sorry, I couldn't find an answer for this question."

        formatted_answer = self.text_processor.escape_markdown(answer)
        if update.effective_chat is None:
            return ValueError("Effective Chat is None")

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=formatted_answer,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
        )

    @staticmethod
    def _is_valid_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        if not update.message.reply_to_message:
            return False

        if context.chat_data is None:
            context.chat_data = {}

        summary_message_id = context.chat_data.get('summary_message_id')
        return update.message.reply_to_message.message_id == summary_message_id

    @staticmethod
    def _create_qa_prompt(messages: List[str], question: str) -> str:
        return "\n".join(messages) + "\n\nQuestion: " + question
