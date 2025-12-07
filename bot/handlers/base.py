"""
Base handler class with shared utilities for all command handlers.
"""
from telegram import Update
from telegram.ext import ContextTypes
from typing import Optional
import logging
from utils.analytics_storage import log_user_event

logger = logging.getLogger(__name__)

# Conversation states for bill splitting
RECEIPT_IMAGE, CONFIRMATION = range(2)


class BaseHandler:
    """Base class for all command handlers with shared utilities."""
    
    def __init__(self, ai_service=None):
        self.ai_service = ai_service
    
    async def safe_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, parse_mode: Optional[str] = None):
        """
        Safely reply to a message, handling cases where update.message might not exist.
        
        Args:
            update: Telegram update object
            context: Telegram context object
            text: Message text to send
            parse_mode: Optional parse mode (e.g., "Markdown", "MarkdownV2")
        
        Returns:
            The sent message or None if unable to send
        """
        if update.message:
            if parse_mode:
                return await update.message.reply_text(text, parse_mode=parse_mode)
            return await update.message.reply_text(text)
        elif update.effective_chat:
            if parse_mode:
                return await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text,
                    parse_mode=parse_mode
                )
            return await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text
            )
        else:
            logger.warning(f"No message or chat found in update for handler.")
            return None
    
    def log_analytics(self, update: Update, event_type: str, llm_name: Optional[str] = None):
        """
        Log a user event to analytics storage.
        
        Args:
            update: Telegram update object
            event_type: Type of event (e.g., "help_command", "summarize_command")
            llm_name: Optional LLM name to log (defaults to current model if ai_service available)
        """
        user = update.effective_user
        chat = update.effective_chat
        
        if user is not None and chat is not None:
            if llm_name is None and self.ai_service:
                llm_name = self.ai_service.get_current_model()
            
            log_user_event(
                user_id=user.id,
                chat_id=chat.id,
                event_type=event_type,
                username=getattr(user, "username", None),
                first_name=getattr(user, "first_name", None),
                last_name=getattr(user, "last_name", None),
                llm_name=llm_name,
            )

