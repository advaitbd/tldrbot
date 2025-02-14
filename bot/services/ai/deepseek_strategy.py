from openai import OpenAI
from config.settings import OpenAIConfig
from services.ai.ai_model_strategy import AIModelStrategy

class DeepSeekStrategy(AIModelStrategy):
    def __init__(self, api_key: str, model: str):
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    def get_response(self, prompt: str) -> str | None:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )

            return response.choices[0].message.content
        except Exception as e:
            return f"An error occurred: {str(e)}"

    def get_current_model(self) -> str:
        return self.model

    def set_model(self, model: str):
        self.model = model
