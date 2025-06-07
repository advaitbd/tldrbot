import logging
from services.ai.ai_service import AIService
from services.ai.openai_strategy import OpenAIStrategy
from config.settings import OpenAIConfig, GroqAIConfig, DeepSeekConfig
from services.ai.groq_strategy import GroqAIStrategy
from services.ai.deepseek_strategy import DeepSeekStrategy

logger = logging.getLogger(__name__)

class StrategyRegistry:
    _strategies = {}

    @classmethod
    def register_strategy(cls, name: str, strategy):
        """Register a strategy with a name."""
        cls._strategies[name] = strategy
        logger.info(f"Registered strategy: {name}")

    @classmethod
    def get_strategy(cls, name: str):
        """Get a strategy by name, with fallback to deepseek if not found."""
        if name not in cls._strategies:
            logger.warning(f"Strategy {name} not found, using deepseek as fallback")
            return cls._strategies.get("deepseek")
        return cls._strategies[name]

    @classmethod
    def available_strategies(cls):
        """Return list of available strategy names."""
        return list(cls._strategies.keys())

# Initialize and register strategies
StrategyRegistry.register_strategy("openai", OpenAIStrategy(OpenAIConfig.API_KEY or "", OpenAIConfig.MODEL or ""))
StrategyRegistry.register_strategy("groq", GroqAIStrategy(GroqAIConfig.API_KEY or "", GroqAIConfig.MODEL or ""))
StrategyRegistry.register_strategy("deepseek", DeepSeekStrategy(DeepSeekConfig.API_KEY or "", DeepSeekConfig.MODEL or ""))
