import openai
import os

# Set API key
openai.api_key = os.environ.get("OPENAI_API_KEY")

def get_summary(result: str) -> str:
    """
    Generate a summary, sentiment, and list of events based on the provided result.

    Args:
        result (str): The input text to be summarized.

    Returns:
        str: The generated summary, sentiment, and events.
    """
    prompt = (
        result
        + '''Based on the above, output the following

                        Summary: [4-5 Sentences]

                        Sentiment: [Choose between, Positive, Negative, Neutral]

                        Events: [List Date, Time and Nature of any upcoming events if there are any]'''
    )

    response = openai.ChatCompletion.create(
        model="gpt-4o", messages=[{"role": "user", "content": prompt}]
    )

    return response["choices"][0]["message"]["content"]

def get_answer_from_gpt(messages: list[str], question: str) -> str:
    """
    Generate an answer to a question based on the provided messages.

    Args:
        messages (list[str]): The list of messages to be used as context.
        question (str): The question to be answered.

    Returns:
        str: The generated answer.
    """
    prompt = "\n".join(messages) + "\n\nQuestion: " + question

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o", messages=[{"role": "system", "content": prompt}]
        )

        answer = response["choices"][0]["message"]["content"]
        return answer
    except Exception as e:
        return f"An error occurred while getting the answer from GPT: {str(e)}"
