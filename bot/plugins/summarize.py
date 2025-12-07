"""Summarize plugin for /tldr command."""
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from plugins import Plugin
from core.ai import AIService
from core.rate_limiter import RateLimiter
from storage.memory import MemoryStorage
import logging

logger = logging.getLogger(__name__)


class SummarizePlugin(Plugin):
    def __init__(self, ai_service: AIService, rate_limiter: RateLimiter, memory: MemoryStorage):
        self.ai = ai_service
        self.rate_limiter = rate_limiter
        self.memory = memory
    
    @property
    def name(self) -> str:
        return "summarize"
    
    @property
    def commands(self):
        return [("tldr", "Summarize recent messages")]
    
    def register(self, app: Application) -> None:
        app.add_handler(CommandHandler("tldr", self.summarize))
    
    async def summarize(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_chat or not update.effective_user:
            return
        
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        if not self.rate_limiter.can_use(user_id):
            await update.message.reply_text(self.rate_limiter.get_limit_message())
            return
        
        num_messages = 50
        if context.args:
            try:
                num_messages = min(max(int(context.args[0]), 1), 400)
            except ValueError:
                pass
        
        messages = self.memory.get_recent_messages(chat_id, num_messages)
        if not messages:
            await update.message.reply_text(
                "🤷 I don't have any messages to summarize. "
                "Either you just added me or everyone's been unusually quiet. "
                "Both are concerning."
            )
            return
        
        progress_msg = await update.message.reply_text(
            "⏳ _Analyzing your chat... This better be worth my time._",
            parse_mode="Markdown"
        )
        
        self.rate_limiter.record_use(user_id)
        remaining = self.rate_limiter.remaining(user_id)
        
        combined_text = "\n".join(messages)
        summary = self.ai.get_summary(combined_text, len(messages))
        
        final_text = f"📝 *Summary* (last {len(messages)} messages)\n\n{summary}"
        if remaining <= 3:
            final_text += f"\n\n⚠️ _You have {remaining} uses left today. Pace yourself._"
        
        try:
            await progress_msg.edit_text(
                final_text,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Failed to edit message: {e}")
            await update.message.reply_text(final_text, parse_mode="Markdown")
        
        self.memory.set_summary_context(chat_id, progress_msg.message_id, messages)
        
        logger.info(f"Summary generated for user {user_id} in chat {chat_id} ({len(messages)} messages)")

