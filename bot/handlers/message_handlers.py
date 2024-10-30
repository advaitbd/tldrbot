from telegram import Update
from telegram.ext import ContextTypes
from services.openai_service import OpenAIService
from utils.text_processor import TextProcessor
import logging

logger = logging.getLogger(__name__)

class MessageHandlers:
    def __init__(self):
        self.openai_service = OpenAIService()
        self.text_processor = TextProcessor()

    async def handle_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_valid_reply(update, context):
            return

        question = update.message.text
        original_messages = context.chat_data.get('original_messages', [])
        
        answer = self.openai_service.get_answer(original_messages, question)
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