import configparser
from telethon.sync import TelegramClient

async def get_chat_history():
    # Read the Telegram API credentials from a config file.
    config = configparser.ConfigParser()
    config.read("config.ini")

    # Retrieve the values from the config file.
    api_id = config["Telegram"]["api_id"]
    api_hash = config["Telegram"]["api_hash"]
    chat_id = int(config["Telegram"]["chat_id"])
    phone = config["Telegram"]["phone_number"]
    
    client = TelegramClient(phone, api_id, api_hash)

    # Start the client.
    await client.start()

    # Get the chat history of the group chat.
    messages = await client.get_messages(chat_id, limit=100)
    result = [f"{message.sender.first_name} {message.sender.last_name}: {message.message} \n"
                  for message in messages if not message.action]
    
    result.reverse()

    for message in result:
        print(message)
    # # Save the chat history to a file.
    # with open("chat_history.txt", "w") as f:
    #     for message in messages:
    #         f.write(message.message + "\n")

    # Close the Telegram client.
    await client.disconnect()

# Run the asynchronous function.
import asyncio

asyncio.run(get_chat_history())
