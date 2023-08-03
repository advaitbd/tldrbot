import logging
from uuid import uuid4
from datetime import datetime
from telegram import __version__ as TG_VER
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, InlineQueryHandler, filters
from utils.history import get_chat_history
from utils.gpt_summarizer import get_summary
import os 

# Env variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT", "5000"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
CALL_COUNT = 0
LAST_RESET_DATE = datetime.now().date()  # Track the last reset date
# Global variable to store the message counts per user
USER_MESSAGE_COUNTS = {}

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! I'm a group chat summarizer bot.",
    )

async def help_command(update: Update, context):
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help!")



async def summarize_command(update: Update, context):
    """Summarize the conversation."""
    global CALL_COUNT, LAST_RESET_DATE, USER_MESSAGE_COUNTS
    current_date = datetime.now().date()

    if LAST_RESET_DATE != current_date:
        # Reset the CALL_COUNT if the dates are different
        LAST_RESET_DATE = current_date
        CALL_COUNT = 0

    CALL_COUNT += 1

    if CALL_COUNT > 20:
        await update.message.reply_text("You have exceeded the maximum number of calls. Please try again later.")
        return

    logger.info("Summarizing conversation...")
    chat_id = update.effective_chat.id

    num_messages = 50  # default value
    if context.args:
        try:
            num_messages = int(context.args[0])
            if num_messages < 1:
                num_messages = 50
        except ValueError:
            await update.message.reply_text("Invalid number of messages. Please provide a valid number.")
    
    # Get user ID and check if it's in the dictionary
    user_id = update.effective_user.id

    if user_id in USER_MESSAGE_COUNTS:
        # If they're at or exceed the limit, don't continue
        if USER_MESSAGE_COUNTS[user_id] + num_messages > 500:
            remaining = 500 - USER_MESSAGE_COUNTS[user_id]
            await context.bot.send_message(
              chat_id=chat_id,
              text=f"You only have {remaining} messages left to summarize.",
            )
            return
        else:
            USER_MESSAGE_COUNTS[user_id] += num_messages
    else:
        USER_MESSAGE_COUNTS[user_id] = num_messages

    

    result = await get_chat_history(chat_id, num_messages)

    caller_info = update.effective_user
    logger.info(f"Conversation summarized by {caller_info.name} ({caller_info.id})")

    prefix = f"_Conversation summarized by {caller_info.name} for last {num_messages} messages:_\n\n"
    postfix = f"\n\n\({CALL_COUNT}/15\) \n\n[made with ❤️ by crustyapples](https://advaitdeshpande.com/)"
    
    summary = prefix + get_summary(result) + postfix
    summary = summary.replace(".", "\.")

    print(summary)
    print("user message counts",USER_MESSAGE_COUNTS)
    await context.bot.send_message(chat_id=chat_id, text=summary, parse_mode="MarkdownV2", disable_web_page_preview=True)


async def inline_query(update: Update, context):
    """Handle inline queries."""
    query = update.inline_query.query
    results = [
        InlineQueryResultArticle(
            id="1",
            title="Summarize Conversation",
            input_message_content=InputTextMessageContent("/summarize"),
        )
    ]

    results = [
        InlineQueryResultArticle(
            id=str(uuid4()),
            title="Summarize Conversation",
            input_message_content=InputTextMessageContent(f"/tldr"),
            description="Summarize the conversation in the group chat",
        ),
        # Add more inline query results for other commands
        InlineQueryResultArticle(
            id=str(uuid4()),
            title="Start",
            input_message_content=InputTextMessageContent(f"/start"),
            description="Start the bot",
        ),
        InlineQueryResultArticle(
            id=str(uuid4()),
            title="Help",
            input_message_content=InputTextMessageContent(f"/help"),
            description="Display help information",
        ),
    ]

    await update.inline_query.answer(results)

def main():
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    # application = Application.builder().token(BOT_TOKEN).build()

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("tldr", summarize_command))

    # Register inline query handler
    application.add_handler(InlineQueryHandler(inline_query))

    if WEBHOOK_URL:
        
        application.run_webhook(listen="0.0.0.0",
                            port=int(PORT),
                            url_path=BOT_TOKEN,
                            webhook_url=os.getenv("WEBHOOK_URL") + BOT_TOKEN)
        logger.info("Application running via webhook: ")

    else:
        application.run_polling()
        logger.info("Application running via polling: ")


if __name__ == "__main__":
    main()
