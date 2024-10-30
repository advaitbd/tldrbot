from typing import List
import openai
from config.settings import OpenAIConfig

class OpenAIService:
    def __init__(self):
        openai.api_key = OpenAIConfig.API_KEY

    def get_summary(self, text: str) -> str:
        prompt = self._create_summary_prompt(text)
        return self._get_completion(prompt)

    def get_answer(self, messages: List[str], question: str) -> str:
        prompt = self._create_qa_prompt(messages, question)
        return self._get_completion(prompt)

    def _get_completion(self, prompt: str) -> str:
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            return response["choices"][0]["message"]["content"]
        except Exception as e:
            return f"An error occurred: {str(e)}"

    @staticmethod
    def _create_summary_prompt(text: str) -> str:
        return (f"{text}\nBased on the above, output the following\n\n"
                "Summary: [4-5 Sentences]\n\n"
                "Sentiment: [Choose between, Positive, Negative, Neutral]\n\n"
                "Events: [List Date, Time and Nature of any upcoming events if there are any]")

    @staticmethod
    def _create_qa_prompt(messages: List[str], question: str) -> str:
        return "\n".join(messages) + "\n\nQuestion: " + question