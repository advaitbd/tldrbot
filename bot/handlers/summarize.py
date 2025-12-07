"""
Summarize command handler for /tldr functionality.
"""
from telegram import Update
from telegram.ext import ContextTypes
import logging
from utils.memory_storage import MemoryStorage
from utils.text_processor import TextProcessor
from services.ai import StrategyRegistry
from services.redis_queue import RedisQueue
from handlers.base import BaseHandler

logger = logging.getLogger(__name__)


class SummarizeHandler(BaseHandler):
    """Handler for /tldr (summarize) command."""
    
    def __init__(self, memory_storage: MemoryStorage, redis_queue: RedisQueue, ai_service=None, model_handler=None):
        super().__init__(ai_service)
        self.memory_storage = memory_storage
        self.redis_queue = redis_queue
        self.model_handler = model_handler  # Reference to ModelHandler for user_selected_model
    
    def _get_user_selected_model(self, user_id: int):
        """Get the user's selected model/provider, or default to 'deepseek'."""
        if self.model_handler:
            return self.model_handler.user_selected_model.get(user_id, "deepseek")
        return "deepseek"
    
    def _get_user_strategy(self, user_id: int, provider: str):
        """Return a strategy for the provider, using user key if available."""
        from services.ai.openai_strategy import OpenAIStrategy
        from services.ai.groq_strategy import GroqAIStrategy
        from services.ai.deepseek_strategy import DeepSeekStrategy
        from config.settings import OpenAIConfig, GroqAIConfig, DeepSeekAIConfig
        from utils.user.user_api_keys import get_user_api_key
        
        provider = provider.lower()
        config_map = {
            "openai-mini": (OpenAIConfig, OpenAIStrategy, OpenAIConfig.MINI_MODEL),
            "openai-4o": (OpenAIConfig, OpenAIStrategy, OpenAIConfig.O4_MODEL),
            "openai-4.1": (OpenAIConfig, OpenAIStrategy, OpenAIConfig.FOUR_ONE_MODEL),
            "groq": (GroqAIConfig, GroqAIStrategy),
            "deepseek": (DeepSeekAIConfig, DeepSeekStrategy),
        }
        
        if provider not in config_map:
            raise ValueError(f"Unknown provider: {provider}")

        mapping = config_map[provider]
        if len(mapping) == 3:
            config_class, strategy_class, model = mapping
        else:
            config_class, strategy_class = mapping
            model = getattr(config_class, 'MODEL', '')

        # Use a shared key for all OpenAI models
        key_provider = 'openai' if provider.startswith('openai') else provider
        user_key = get_user_api_key(user_id, key_provider)
        key = user_key if user_key is not None else (config_class.API_KEY if getattr(config_class, 'API_KEY', None) is not None else "")

        return strategy_class(key, model)
    
    async def summarize(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /tldr command."""
        self.log_analytics(update, "summarize_command")

        if not update.effective_chat or not hasattr(update.effective_chat, "id"):
            logger.error("No effective_chat or chat id found in update.")
            await self.safe_reply(update, context, "Could not determine chat context.")
            return

        chat_id = update.effective_chat.id
        num_messages = self._parse_message_count(getattr(context, "args", None), default=50, max_limit=400)

        if not num_messages:
            await self.safe_reply(update, context, "Invalid message count")
            return

        messages_list = self.memory_storage.get_recent_messages(chat_id, num_messages)
        combined_text = "\n".join(messages_list)
        summary_prompt = self._create_summary_prompt(combined_text)

        # Immediately reply to user
        await self.safe_reply(update, context, "Summarizing... I'll send the summary here when it's ready! 📝")

        # Use user's selected model/provider and key if available
        user = update.effective_user
        provider = self._get_user_selected_model(user.id if user is not None else 0)
        try:
            strategy = self._get_user_strategy(user.id if user is not None else 0, provider)
            self.ai_service.set_strategy(strategy)  # pyright: ignore[reportOptionalMemberAccess]
        except Exception as e:
            logger.error(f"Error setting user strategy: {str(e)}")
            # fallback to default
            self.ai_service.set_strategy(StrategyRegistry.get_strategy("deepseek"))  # pyright: ignore[reportOptionalMemberAccess]

        # Enqueue the LLM job in Redis
        job_data = {
            "type": "tldr",
            "chat_id": chat_id,
            "user_id": user.id if user else None,
            "prompt": summary_prompt,
            "num_messages": num_messages,
            "original_messages": messages_list,
        }
        await self.redis_queue.enqueue(job_data)

        # Optionally: store job info in context for tracking
        if not hasattr(context, "chat_data") or context.chat_data is None:
            context.chat_data = {}
        context.chat_data['pending_tldr'] = True
    
    @staticmethod
    def _parse_message_count(args, default: int, max_limit: int) -> int:
        if not args:
            return default
        try:
            count = int(args[0])
            return min(max(count, 1), max_limit)
        except ValueError:
            return default

    def _create_summary_prompt(self, text: str) -> str:
        return (f"{text}\nBased on the above, output the following\n\n"
                "Summary: [4-5 Sentences]\n\n"
                "Sentiment: [Choose between, Positive, Negative, Neutral]\n\n"
                "Events: [List Date, Time and Nature of any upcoming events if there are any]")

    def _format_summary(self, summary: str, user_name: str, message_count: int) -> str:
        return TextProcessor.format_summary_message(summary, user_name, message_count)

