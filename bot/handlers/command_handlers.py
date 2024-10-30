from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from uuid import uuid4
from telegram.ext import ContextTypes
from services.openai_service import OpenAIService
from utils.chat_history import ChatHistoryManager
from utils.text_processor import TextProcessor
import logging

logger = logging.getLogger(__name__)

class CommandHandlers:
    def __init__(self):
        self.openai_service = OpenAIService()
        self.history_manager = ChatHistoryManager()
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Hello! I'm TLDR Bot. How can I help you today?")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("I'm TLDR Bot. I can summarize conversations and answer questions. Use /tldr to summarize a conversation and /help to see this message again.")

    async def summarize(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        num_messages = self._parse_message_count(context.args, default=50, max_limit=400)
        
        if not num_messages:
            await update.message.reply_text("Invalid message count")
            return

        try:
            result = await self.history_manager.get_chat_history(chat_id, num_messages)
            summary = self.openai_service.get_summary(result)
            formatted_summary = self._format_summary(summary, update.effective_user, num_messages)
            
            summary_message = await context.bot.send_message(
                chat_id=chat_id,
                text=formatted_summary,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True,
            )

            # Store context for follow-up questions
            context.chat_data['summary_message_id'] = summary_message.message_id
            context.chat_data['original_messages'] = result

        except Exception as e:
            logger.error(f"Message formatting error: {str(e)}")
            # Fallback to plain text if markdown parsing fails
            await context.bot.send_message(
                chat_id=chat_id,
                text=summary,
                disable_web_page_preview=True,
            )

    async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline queries."""
        query = update.inline_query.query
        results = [
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="Summarize Conversation",
                input_message_content=InputTextMessageContent(f"/tldr"),
                description="Summarize the conversation in the group chat",
            ),
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="Start",
                input_message_content=InputTextMessageContent(f"/start"),
                description="Start the bot",
            ),
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="Help",
                input_message_content=InputTextMessageContent(f"/help"),
                description="Display help information",
            ),
        ]
        
        await update.inline_query.answer(results)



    @staticmethod
    def _parse_message_count(args, default: int, max_limit: int) -> int:
        if not args:
            return default
        try:
            count = int(args[0])
            return min(max(count, 1), max_limit)
        except ValueError:
            return None
        
    def _format_summary(self, summary: str, user_name: str, message_count: int) -> str:
        return TextProcessor.format_summary_message(summary, user_name, message_count)