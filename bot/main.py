import logging
from uuid import uuid4
from telegram import __version__ as TG_VER
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, MessageHandler, InlineQueryHandler, filters
from utils.history import get_chat_history
from utils.gpt_summarizer import get_summary
# from utils.davinci_summarizer import get_summary
import os 

# Env variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT", "5000"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

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
    logger.info("Summarizing conversation...")
    chat_id = update.effective_chat.id
    result = await get_chat_history(chat_id)
    summary = get_summary(result)
    # Send the summary as a message in the chat
    await context.bot.send_message(chat_id=chat_id, text=summary)


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
    application.add_handler(CommandHandler("tldr", summarize_command))

    # Register inline query handler
    application.add_handler(InlineQueryHandler(inline_query))

    if WEBHOOK_URL:
        application.run_webhook(listen="0.0.0.0",
                            port=int(PORT),
                            url_path=BOT_TOKEN,
                            webhook_url=os.getenv("WEBHOOK_URL") + BOT_TOKEN)
        logger.info("Application running via webhook: ", BOT_TOKEN)

    else:
        application.run_polling()
        logger.info("Application running via polling: ", BOT_TOKEN)


if __name__ == "__main__":
    main()
