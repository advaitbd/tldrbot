from telethon.sync import TelegramClient, events
from telethon.errors.rpcerrorlist import PhoneNumberInvalidError

api_id = 2954792
api_hash = "c3efacabe4b91251c8d50e8e98c9a573"
bot_token = '1433555369:AAF4KbunZ69OB7-DOIy6TpJBRSvnOrLvXYc'

client = TelegramClient('handler_session', api_id, api_hash)
bot = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

async def login(user_phone_number):
    try:
        await client.start(phone=user_phone_number)
        me = await client.get_me()
        user_is_signed_in = True
        return user_is_signed_in, me.first_name
    except PhoneNumberInvalidError:
        user_is_signed_in = False
        return user_is_signed_in, None

@bot.on(events.NewMessage(pattern='/login'))
async def login_handler(event):
    chat_id = event.chat_id

    # Ask user for the phone number
    await bot.send_message(chat_id, "Please provide your phone number to log in, including the country code:")
    phone_number_event = await bot.wait_event(events.NewMessage(chats=chat_id))
    phone_number = phone_number_event.message.message

    logged_in, name = await login(phone_number)

    if logged_in:
        await bot.send_message(chat_id, f'Logged in as {name}')
    else:
        await bot.send_message(chat_id, f'Login failed: Invalid phone number.')

def main():
    with client, bot:
        client.run_until_disconnected()

if __name__ == '__main__':
    main()