import openai
import os

openai.api_key = config["OpenAI"]["api_key"]
openai.api_key = os.environ.get("OPENAI_API_KEY")


def get_summary(result):
    # Define prompt
    prompt = (
        result
        + '''Based on the above, output the following

                        "Summary: [4-5 Sentences]

                        Sentiment: [Choose between, Positive, Negative, Neutral]

                        Events: [List Date, Time and Nature of any upcoming events if there are any]"'''
    )

    # Call API and receive response
    generated = openai.ChatCompletion.create(
        model="gpt-4o", messages=[{"role": "user", "content": f"{prompt}"}]
    )

    # Output summary to console
    return generated["choices"][0]["message"]["content"]
