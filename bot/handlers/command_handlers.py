from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from uuid import uuid4
from telegram.ext import ContextTypes
from telethon.sessions import memory
from utils.memory_storage import MemoryStorage
from services.openai_service import OpenAIService
from utils.text_processor import TextProcessor
import logging

logger = logging.getLogger(__name__)

class CommandHandlers:
    def __init__(self, memory_storage: MemoryStorage):
        self.openai_service = OpenAIService()
        self.memory_storage = memory_storage

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
            memory_storage = self.memory_storage
            messages_list = memory_storage.get_recent_messages(chat_id, num_messages)
            combined_text = "\n".join(messages_list)
            summary = self.openai_service.get_summary(combined_text)
            formatted_summary = self._format_summary(summary, update.effective_user, num_messages)

            summary_message = await context.bot.send_message(
                chat_id=chat_id,
                text=formatted_summary,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True,
            )

            # Store context for follow-up questions
            context.chat_data['summary_message_id'] = summary_message.message_id
            context.chat_data['original_messages'] = messages_list

        except Exception as e:
            logger.error(f"Message formatting error: {str(e)}")
            # Fallback to plain text if markdown parsing fails
            await context.bot.send_message(
                chat_id=chat_id,
                text=str(summary),
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
