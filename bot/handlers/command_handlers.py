from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from uuid import uuid4
from telegram.ext import ContextTypes
from services.ai import StrategyRegistry
from utils.memory_storage import MemoryStorage
from services.ai.ai_service import AIService
from utils.text_processor import TextProcessor
import logging
from config.settings import OpenAIConfig, GroqAIConfig

logger = logging.getLogger(__name__)

class CommandHandlers:
    def __init__(self, memory_storage: MemoryStorage):
        self.memory_storage = memory_storage
        self.ai_service = AIService(StrategyRegistry.get_strategy("deepseek"))

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "🤖 *Welcome to TLDR Bot!* 🤖\n\n"
            "I help you summarize conversations and provide insights. Here's what I can do:\n\n"
            "*Commands:*\n"
            "• `/tldr [number]` - Summarize the last [number] messages (default: 50)\n"
            "• `/dl [URL]` - Download TikToks, Reels, Shorts, etc. (WIP: might not work sometimes)\n"
            "• `/switch_model [model]` - Change the AI model\n"
            "\n*Available Models:*\n"
            "• `groq` - Uses Llama 3 (8bn) hosted by groq\n"
            "• `deepseek` - DeepSeek V3\n"
            "\n*Features:*\n"
            "• Reply to my summaries with questions for more insights\n"
            "• View sentiment analysis in summaries\n"
            "• Get key events extracted from conversations\n"
            "\n*Current model:* " + self.ai_service.get_current_model()
        )

        await update.message.reply_text(help_text, parse_mode="Markdown")

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

        new_model = context.args[0]

        available_models = StrategyRegistry.available_strategies()
        if new_model not in available_models:
            await update.message.reply_text(f"Invalid model name. Available models: {', '.join(available_models)}")
            return

        try:
            strategy = StrategyRegistry.get_strategy(new_model)
            self.ai_service.set_strategy(strategy)
            await update.message.reply_text(f"Model switched to {new_model}")

        except Exception as e:
            logger.error(f"Error switching model: {str(e)}")
            await update.message.reply_text(f"Failed to switch model: {str(e)}")

    async def inline_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
