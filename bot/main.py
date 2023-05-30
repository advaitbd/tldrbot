import logging
from uuid import uuid4
from telegram import __version__ as TG_VER
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, MessageHandler, InlineQueryHandler, filters

import os 

# Tokens
BOT_TOKEN = os.environ.get("BOT_TOKEN")
print(BOT_TOKEN)


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
    chat_id = update.effective_chat.id
    # Retrieve the messages in the group chat within a specific time range
    # Here, you can use the update.message or update.effective_chat to access necessary information
    start_date = ...  # Specify the start date for the conversation summary
    end_date = ...  # Specify the end date for the conversation summary
    # Query the messages within the given time range
    # messages = context.bot.get_chat_history(chat_id, start_date, end_date
    messages = "Blablabla"
    # Process the messages and generate the summary
    summary = generate_summary(messages)
    # Send the summary as a message in the chat
    await context.bot.send_message(chat_id=chat_id, text=summary)

def generate_summary(messages):
    # Your code for generating the summary based on the retrieved messages goes here
    # Return the generated summary
    return "This is a summary of the conversation."

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
            input_message_content=InputTextMessageContent(f"/summarize"),
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
    application = Application.builder().token(BOT_TOKEN).build()

    # Check the PTB version compatibility
    if TG_VER < "20.0.0":
        raise RuntimeError(
            f"This example is not compatible with your current PTB version {TG_VER}. "
            "To view the latest example, visit "
            "https://docs.python-telegram-bot.org/en/stable/examples.html"
        )

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("summarize", summarize_command))

    # Register inline query handler
    application.add_handler(InlineQueryHandler(inline_query))

    # Run the bot
    application.run_polling()


if __name__ == "__main__":
    main()
