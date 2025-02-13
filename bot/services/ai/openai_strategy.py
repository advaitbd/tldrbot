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

    def get_image_response(self, prompt: str) -> str | None:
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": '''You will be provided with an image of a PDF page or a slide. Your goal is to deliver a detailed and engaging presentation about the content you see, using clear and accessible language suitable for a 101-level audience.

                    If there is an identifiable title, start by stating the title to provide context for your audience.

                    Describe visual elements in detail:

                    - **Diagrams**: Explain each component and how they interact. For example, "The process begins with X, which then leads to Y and results in Z."

                    - **Tables**: Break down the information logically. For instance, "Product A costs X dollars, while Product B is priced at Y dollars."

                    Focus on the content itself rather than the format:

                    - **DO NOT** include terms referring to the content format.

                    - **DO NOT** mention the content type. Instead, directly discuss the information presented.

                    Keep your explanation comprehensive yet concise:

                    - Be exhaustive in describing the content, as your audience cannot see the image.

                    - Exclude irrelevant details such as page numbers or the position of elements on the image.

                    Use clear and accessible language:

                    - Explain technical terms or concepts in simple language appropriate for a 101-level audience.

                    Engage with the content:

                    - Interpret and analyze the information where appropriate, offering insights to help the audience understand its significance.

                    ------

                    If there is an identifiable title, present the output in the following format:

                    {TITLE}

                    {Content description}

                    If there is no clear title, simply provide the content description.
                    '''},

                    {"role": "user", "content": [
                                    {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"{prompt}"
                                    }
                                    }
                                ]}]
            )

            return response["choices"][0]["message"]["content"]
        except Exception as e:
            return f"An error occurred: {str(e)}"

    def get_current_model(self) -> str:
        return self.model

    def set_model(self, model: str):
        self.model = model
