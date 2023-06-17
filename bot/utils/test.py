from history import get_chat_history
from gpt_summarizer import get_summary
import bert_summarizer
import davinci_summarizer
import asyncio
import configparser

config = configparser.ConfigParser()
config.read("config.ini")
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