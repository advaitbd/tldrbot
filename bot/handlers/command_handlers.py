from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from uuid import uuid4
from telegram.ext import ContextTypes
from utils.memory_storage import MemoryStorage
from services.ai.openai_strategy import OpenAIStrategy
from services.ai.groq_strategy import GroqAIStrategy
from services.ai.ai_service import AIService
from utils.text_processor import TextProcessor
import logging
from config.settings import OpenAIConfig, GroqAIConfig

logger = logging.getLogger(__name__)

class CommandHandlers:
    def __init__(self, memory_storage: MemoryStorage):
        openai_strategy = OpenAIStrategy(OpenAIConfig.API_KEY, OpenAIConfig.MODEL)
        self.ai_service = AIService(openai_strategy)
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
            summary = self._create_summary_prompt(combined_text)
            response = self.ai_service.get_response(summary)
            formatted_summary = self._format_summary(response, update.effective_user, num_messages)

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
                text=str(response),
                disable_web_page_preview=True,
            )

    async def switch_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Please provide a model name.")
            return

        openai_strategy = OpenAIStrategy(OpenAIConfig.API_KEY, OpenAIConfig.MODEL)
        groq_strategy = GroqAIStrategy(GroqAIConfig.API_KEY, GroqAIConfig.MODEL)

        new_model = context.args[0]

        available_models = ["openai", "groq"]
        if new_model not in available_models:
            await update.message.reply_text(f"Invalid model name. Available models: {', '.join(available_models)}")
            return

        if new_model == "openai":
            self.ai_service.set_strategy(openai_strategy)
        else:
            self.ai_service.set_strategy(groq_strategy)

        await update.message.reply_text(f"Model switched to {new_model}")

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

    def _create_summary_prompt(self, text: str) -> str:
        return (f"{text}\nBased on the above, output the following\n\n"
                "Summary: [4-5 Sentences]\n\n"
                "Sentiment: [Choose between, Positive, Negative, Neutral]\n\n"
                "Events: [List Date, Time and Nature of any upcoming events if there are any]")

    def _format_summary(self, summary: str, user_name: str, message_count: int) -> str:
        return TextProcessor.format_summary_message(summary, user_name, message_count)
