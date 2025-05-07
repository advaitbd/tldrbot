from services.ai.openai_strategy import OpenAIStrategy
from services.ai.groq_strategy import GroqAIStrategy
from services.ai.deepseek_strategy import DeepSeekStrategy
from services.ai.ai_model_strategy import AIModelStrategy
from config.settings import OpenAIConfig, GroqAIConfig, DeepSeekAIConfig

class StrategyRegistry:
    _strategies = {}

    @classmethod
    def register_strategy(cls, name: str, strategy: AIModelStrategy):
        cls._strategies[name] = strategy

    @classmethod
    @classmethod
    def get_strategy(cls, name: str) -> AIModelStrategy:
        strategy = cls._strategies.get(name)
        if strategy is None:
            raise ValueError(f"Strategy '{name}' not found.")
        return strategy

    @classmethod
    def available_strategies(cls) -> list[str]:
        return list(cls._strategies.keys())

# Register strategies with their respective API keys and models
api_key = OpenAIConfig.API_KEY or ""
model = OpenAIConfig.MODEL or ""
StrategyRegistry.register_strategy("openai", OpenAIStrategy(api_key, model))
StrategyRegistry.register_strategy("groq", GroqAIStrategy(GroqAIConfig.API_KEY or "", GroqAIConfig.MODEL or ""))
StrategyRegistry.register_strategy("deepseek", DeepSeekStrategy(DeepSeekAIConfig.API_KEY or "", DeepSeekAIConfig.MODEL or ""))
