"""Mention reply plugin."""
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters
from plugins import Plugin
from core.ai import AIService
from core.rate_limiter import RateLimiter
from storage.memory import MemoryStorage
import logging

logger = logging.getLogger(__name__)


class MentionReplyPlugin(Plugin):
    def __init__(self, ai_service: AIService, rate_limiter: RateLimiter, memory: MemoryStorage):
        self.ai = ai_service
        self.rate_limiter = rate_limiter
        self.memory = memory
        self.bot_username: str | None = None
    
    @property
    def name(self) -> str:
        return "mention_reply"
    
    def register(self, app: Application) -> None:
        app.post_init = self._store_bot_username
        app.add_handler(MessageHandler(
            filters.TEXT & filters.Entity("mention"),
            self.handle_mention
        ))
        app.add_handler(MessageHandler(
            filters.REPLY & filters.TEXT,
            self.handle_reply
        ))
    
    async def _store_bot_username(self, app: Application) -> None:
        bot_info = await app.bot.get_me()
        self.bot_username = f"@{bot_info.username}".lower()
        logger.info(f"Bot username stored: {self.bot_username}")
    
    async def handle_mention(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text or not update.effective_user:
            return
        if not self.bot_username:
            return
        if self.bot_username not in update.message.text.lower():
            return
        await self._respond_to_user(update, context)
    
    async def handle_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.reply_to_message:
            return
        reply_to = update.message.reply_to_message
        if not reply_to.from_user or not reply_to.from_user.is_bot:
            return
        if self.bot_username and f"@{reply_to.from_user.username}".lower() != self.bot_username:
            return
        
        await self._respond_to_user(update, context)
    
    async def _respond_to_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not update.effective_chat:
            return
        
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        if not self.rate_limiter.can_use(user_id):
            await update.message.reply_text(self.rate_limiter.get_limit_message())
            return
        
        user_message = update.message.text
        if self.bot_username and user_message:
            user_message = user_message.replace(self.bot_username, "").replace(
                self.bot_username.replace("@", ""), ""
            ).strip()
        if not user_message:
            user_message = "Hey"
        
        recent_messages = self.memory.get_recent_messages(chat_id, 20)
        context_text = "\n".join(recent_messages[-10:]) if recent_messages else None
        
        self.rate_limiter.record_use(user_id)
        response = self.ai.get_mention_response(user_message, context_text)
        
        await update.message.reply_text(response)
        
        remaining = self.rate_limiter.remaining(user_id)
        if remaining <= 2:
            await update.message.reply_text(
                f"_({remaining} uses left today. Just so you know.)_",
                parse_mode="Markdown"
            )
        
        logger.info(f"Mention response sent to user {user_id}")

