import openai
from config.settings import OpenAIConfig
from services.ai.ai_model_strategy import AIModelStrategy

class OpenAIStrategy(AIModelStrategy):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        openai.api_key = self.api_key

    def get_response(self, prompt: str) -> str | None:
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )

            return response["choices"][0]["message"]["content"]
        except Exception as e:
            return f"An error occurred: {str(e)}"

    def get_current_model(self) -> str:
        return self.model

    def set_model(self, model: str):
        self.model = model
