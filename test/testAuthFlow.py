from telethon import TelegramClient
from telethon.sessions import StringSession
import asyncio

API_ID = 0
API_HASH = ""
STRING = ""
client = TelegramClient(StringSession(STRING), API_ID, API_HASH)

async def get_code():
    await client.connect()
    phone = "PHONE_NUMBER"
    # This will send the code to the user. You have to get it using the front end
    phone_code = await client.send_code_request(phone)
    phone_code_hash = phone_code.phone_code_hash

    return phone_code_hash, phone

async def login(phone,phone_code_hash, code):
    try:
        await client.sign_in(phone, code=code, phone_code_hash=phone_code_hash)
    except Exception as e:
        print(f"2FA enabled {phone}: {e}")
        password = input("Enter password: ")
        print(password)
        await client.sign_in(phone, password=password)


async def main():
    phone_code_hash, phone = await get_code()
    code = input("Enter code: ")
    await login(phone, phone_code_hash, code)

    messages = await client.get_messages(-885033485, limit=100)
    result = [f"{message.sender.first_name}: {message.message} \n" for message in messages if not message.action]
    print(result)


# with client:
#     client.loop.run_until_complete(main())

asyncio.run(main())