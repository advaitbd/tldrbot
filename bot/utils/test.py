from history import get_chat_history
from gpt_summarizer import get_summary
import bert_summarizer
import davinci_summarizer
import asyncio
import configparser
import os

config = configparser.ConfigParser()
current_dir = os.path.dirname(os.path.abspath(__file__))
config_file_path = os.path.join(current_dir, "config.ini")
config.read(config_file_path)
chat_id = int(config["Telegram"]["ITUS"])


async def main():
    result = await get_chat_history(chat_id)
    print(result)
    # Prompt User for Model
    model = input("Which model would you like to use? (gpt, bert, davinci): ")

    if model == "gpt":
        summary = get_summary(result)
    elif model == "bert":
        summary = bert_summarizer.get_summary(result)
    elif model == "davinci":
        summary = davinci_summarizer.get_summary(result)

    print(summary)


if __name__ == "__main__":

    asyncio.run(main())
