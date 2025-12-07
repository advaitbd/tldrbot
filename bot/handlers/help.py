"""
Help command handler and inline query handler.
"""
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from uuid import uuid4
from telegram.ext import ContextTypes
import logging
from handlers.base import BaseHandler

logger = logging.getLogger(__name__)


class HelpHandler(BaseHandler):
    """Handler for /help command and inline queries."""
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        self.log_analytics(update, "help_command")

        help_text = (
            "🤖 *Welcome to TLDR Bot!* 🤖\n\n"
            "I help you summarize conversations and provide insights. Here's what I can do:\n\n"
            "*Commands:*\n"
            "• `/tldr [number]` — Summarize the last [number] messages (default: 50)\n"
            "• `/dl [URL]` — Download TikToks, Reels, Shorts, etc. (WIP: might not work sometimes)\n"
            "• `/switch_model <provider>` — Change the AI model\n"
            "• `/set_api_key <provider> <key>` — Set your own API key for a provider (BYOK)\n"
            "    Valid providers: `openai`, `groq`, `deepseek`\n"
            "• `/clear_api_key <provider>` — Remove your API key for a provider\n"
            "    Valid providers: `openai`, `groq`, `deepseek`\n"
            "• `/list_providers` — List all valid provider names\n"
            "• `/set_receipt_model <model>` — Choose OpenAI model for receipt parsing\n"
            "\n*Available Models:*\n"
            "• `openai-mini` — GPT-4o mini\n"
            "• `openai-4o` — GPT-4o\n"
            "• `openai-4.1` — GPT-4.1 (turbo)\n"
            "• `groq` — Uses Llama 3 (8bn) hosted by groq\n"
            "• `deepseek` — DeepSeek V3\n"
            "\n*Features:*\n"
            "• Reply to my summaries with questions for more insights\n"
            "• View sentiment analysis in summaries\n"
            "• Get key events extracted from conversations\n"
            "\n*Current model:* " + str(self.ai_service.get_current_model())
        )

        await self.safe_reply(update, context, help_text, parse_mode="Markdown")

    async def inline_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline queries."""
        if not hasattr(update, "inline_query") or update.inline_query is None:
            logger.warning("No inline_query found in update for inline_query handler.")
            return

        query = getattr(update.inline_query, "query", "")
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

        if hasattr(update.inline_query, "answer") and callable(update.inline_query.answer):
            await update.inline_query.answer(results)
        else:
            logger.warning("inline_query.answer is not available on update.inline_query.")

