import logging
from telegram import __version__ as TG_VER
from telegram import Update, ForceReply
from telegram.ext import Application, CommandHandler, MessageHandler, filters
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
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )

async def help_command(update: Update, context):
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help!")

async def summarize_command(update: Update, context):
    """Summarize the conversation."""
    # Your code for summarizing the conversation goes here
    # You can use update.message or update.effective_chat to access the necessary information
    # Generate the summary
    summary = "This is a summary of the conversation."
    # Send the summary as a message in the chat
    await update.message.reply_text(summary)

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

    # Run the bot
    application.run_polling()


if __name__ == "__main__":
    main()
