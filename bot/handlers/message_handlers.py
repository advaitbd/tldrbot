from telegram import Update
from telegram.ext import ContextTypes
from utils.text_processor import TextProcessor
import logging
from services.ai.openai_strategy import OpenAIStrategy
from services.ai.ai_service import AIService
from config.settings import OpenAIConfig
from typing import List

logger = logging.getLogger(__name__)

class MessageHandlers:
    def __init__(self):
        openai_strategy = OpenAIStrategy(OpenAIConfig.API_KEY, OpenAIConfig.MODEL)
        self.ai_service = AIService(openai_strategy)
        self.text_processor = TextProcessor()

    async def handle_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_valid_reply(update, context):
            return

        question = update.message.text
        original_messages = context.chat_data.get('original_messages', [])
        prompt = self._create_qa_prompt(original_messages, question)
        answer = self.ai_service.get_response(prompt)
        formatted_answer = self.text_processor.escape_markdown(answer)

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

        summary_message_id = context.chat_data.get('summary_message_id')
        return update.message.reply_to_message.message_id == summary_message_id

    @staticmethod
    def _create_qa_prompt(messages: List[str], question: str) -> str:
        return "\n".join(messages) + "\n\nQuestion: " + question
