from openai.api_resources import chat_completion
from config.settings import GroqAIConfig
from services.ai.ai_model_strategy import AIModelStrategy
from groq import Groq

class GroqAIStrategy(AIModelStrategy):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.client = Groq(api_key=self.api_key)

    def get_response(self, prompt: str) -> str | None:
        try:
            chat_completion = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )

            return chat_completion.choices[0].message.content

        except Exception as e:
            return f"An error occurred: {str(e)}"

    def get_current_model(self) -> str:
        return self.model

    def set_model(self, model: str):
        self.model = model
