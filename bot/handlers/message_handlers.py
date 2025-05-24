from telegram import Update
from telegram.ext import ContextTypes
from utils.text_processor import TextProcessor
import logging
import time
from services.ai.ai_service import AIService
from services.ai import StrategyRegistry
from config.settings import OpenAIConfig
from typing import List

# Import freemium services
from services.usage_service import UsageService
from utils.user_management import is_premium

logger = logging.getLogger(__name__)

class MessageHandlers:
    def __init__(self, memory_storage=None):
        self.ai_service = AIService(StrategyRegistry.get_strategy("deepseek"))
        self.text_processor = TextProcessor()
        self.memory_storage = memory_storage
        
        # Initialize freemium services
        self.usage_service = UsageService()

    async def handle_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id if update.effective_chat else None
        summary_context = None
        if self.memory_storage and chat_id is not None:
            summary_context = self.memory_storage.get_summary_context(chat_id)
        if not self._is_valid_reply(update, summary_context):
            return

        if update.message is None or update.message.text is None:
            logger.error("No message or message text found in update")
            return

        # FREEMIUM: Check quota before processing (reply-to-summary uses AI services)
        user = update.effective_user
        
        if user and chat_id:
            try:
                # Track performance for quota checks
                quota_start_time = time.time()
                
                # Check if user is within quota
                within_quota = await self.usage_service.within_quota(user.id, chat_id)
                
                # Log performance metrics
                quota_end_time = time.time()
                quota_duration = (quota_end_time - quota_start_time) * 1000  # Convert to ms
                
                if quota_duration > 50:  # Log if quota check took longer than 50ms
                    logger.warning(f"Quota check took {quota_duration:.2f}ms for reply user {user.id}")
                else:
                    logger.debug(f"Quota check completed in {quota_duration:.2f}ms for reply user {user.id}")
                
                if not within_quota:
                    # For replies, we'll send a simple message instead of deleting
                    # since this is a reply to a summary, not a command
                    await update.message.reply_text(
                        "🔒 You've reached your daily limit. Use /upgrade for unlimited access."
                    )
                    return
                    
            except Exception as e:
                logger.error(f"Error checking quota for reply user {user.id}: {e}")
                # Fail-safe: allow premium users, block others
                if not is_premium(user.id):
                    await update.message.reply_text("Service temporarily unavailable. Please try again later.")
                    return

        question = update.message.text
        original_messages = summary_context["original_messages"] if summary_context else []
        prompt = self._create_qa_prompt(original_messages, question)
        
        # FREEMIUM: Increment usage counters for successful requests
        if user and chat_id:
            try:
                counters = await self.usage_service.increment_counters(user.id, chat_id)
                logger.info(f"Updated usage counters for reply user {user.id}: {counters}")
            except Exception as e:
                logger.error(f"Error incrementing counters for reply user {user.id}: {e}")
        
        answer = self.ai_service.get_response(prompt)

        if answer is None:
            logger.error("Failed to get response from AI service")
            answer = "Sorry, I couldn't find an answer for this question."

        formatted_answer = self.text_processor.escape_markdown(answer)
        if update.effective_chat is None:
            logger.error("Effective Chat is None")
            return

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=formatted_answer,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
        )

    @staticmethod
    def _is_valid_reply(update: Update, summary_context) -> bool:
        if update.message is None or update.message.reply_to_message is None:
            return False

        if not summary_context or "summary_message_id" not in summary_context:
            return False

        summary_message_id = summary_context["summary_message_id"]
        return update.message.reply_to_message.message_id == summary_message_id

    @staticmethod
    def _create_qa_prompt(messages: List[str], question: str) -> str:
        return "\n".join(messages) + "\n\nQuestion: " + question
