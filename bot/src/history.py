from .telegram_client import get_telegram_client
from .message_filter import filter_bot_messages
from .message_processor import censor_result
from .config import censor_list

async def get_chat_history(chat_id, num_messages):
    client = await get_telegram_client()
    messages = await client.get_messages(chat_id, limit=num_messages)

    result = [
        f"{message.sender.first_name}: {message.message} \n"
        for message in messages
        if not message.action
    ]

    censored_result = censor_result(result, censor_list)
    filtered_result = filter_bot_messages(censored_result)
    filtered_result.reverse()

    await client.disconnect()
    return "\n".join(filtered_result)
