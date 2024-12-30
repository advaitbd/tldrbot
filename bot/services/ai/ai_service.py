from services.ai.ai_model_strategy import AIModelStrategy

class AIService:
    def __init__(self, strategy: AIModelStrategy):
        self._strategy = strategy

    def set_strategy(self, strategy: AIModelStrategy):
        self._strategy = strategy

    def get_response(self, prompt: str) -> str | None:
        return self._strategy.get_response(prompt)

    def get_current_model(self) -> str:
        return self._strategy.get_current_model()
