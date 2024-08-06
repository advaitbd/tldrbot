import openai
import os

openai.api_key = config["OpenAI"]["api_key"]
openai.api_key = os.environ.get("OPENAI_API_KEY")

def get_summary(result):
    # Define prompt
    prompt = (
        f"Analyze the following text and provide a summary, sentiment, and any upcoming events mentioned.\n\n"
        f"Text: {result}\n\n"
        "Output in the following format without any quotes:\n"
        "Summary: [4-5 sentences summarizing the text]\n"
        "Sentiment: [Positive, Negative, Neutral]\n"
        "Events: [List Date, Time, and Nature of any upcoming events if mentioned]\n"
    )

    # Call API and receive response
    generated = openai.ChatCompletion.create(
        model="gpt-4o", messages=[{"role": "user", "content": f"{prompt}"}]
    )

    # Output summary to console
    return generated["choices"][0]["message"]["content"]
