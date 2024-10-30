import logging
from uuid import uuid4
from datetime import datetime
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    InlineQueryHandler,
    filters,
)
from utils.history import get_chat_history
from utils.gpt_summarizer import get_summary, get_answer_from_gpt
import os
import yt_dlp
import openai

# Env variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT", "5000"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    if user:
        await update.message.reply_html(
            rf"Hi {user.mention_html()}! I'm a group chat summarizer bot.",
        )
    else:
        await update.message.reply_text("Hi! I'm a group chat summarizer bot.")

async def help_command(update: Update, context):
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help!")

async def summarize_command(update: Update, context):
    """Summarize the conversation."""
    logger.info("Summarizing conversation...")
    chat_id = update.effective_chat.id if update.effective_chat else None

    if chat_id is None:
        await update.message.reply_text("Error: Unable to get chat ID.")
        return

    num_messages = 50  # default value
    if context.args:
        try:
            num_messages = int(context.args[0])
            if num_messages < 1:
                num_messages = 50
            if num_messages >= 400:
                await update.message.reply_text(
                    "Too many messages. Please provide a number less than 400."
                )
                return
        except ValueError:
            await update.message.reply_text(
                "Invalid number of messages. Please provide a valid number."
            )
            return

    try:
        result = await get_chat_history(chat_id, num_messages)
    except Exception as e:
        logger.error(e)
        await context.bot.send_message(
            chat_id=chat_id,
            text="An error occurred. Please try reducing the number of messages.",
        )
        return

    caller_info = update.effective_user
    if caller_info:
        logger.info(f"Conversation summarized by {caller_info.name} ({caller_info.id})")
        prefix = f"_Conversation summarized by {caller_info.name} for the last {num_messages} messages:_\n\n"
    else:
        prefix = f"_Conversation summarized for the last {num_messages} messages:_\n\n"

    postfix = ""

    summary = prefix + get_summary(result) + postfix
    summary = summary.replace(".", "\\.")
    summary = summary.replace("-", "\\-")
    summary = summary.replace("(", "\\(")
    summary = summary.replace(")", "\\)")

    summary_message = await context.bot.send_message(
        chat_id=chat_id,
        text=summary,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )

    # Store the summary message ID and original messages in the context
    context.chat_data['summary_message_id'] = summary_message.message_id
    context.chat_data['original_messages'] = result

async def handle_reply(update: Update, context):
    """Handle replies to the summary message."""
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        logger.error("Chat ID is None")
        return

    logger.info("Received a reply message")

    # Check if the message is a reply to the summary
    if update.message.reply_to_message:
        logger.info("Message is a reply to another message")
        if update.message.reply_to_message.message_id == context.chat_data.get('summary_message_id'):
            logger.info("Message is a reply to the summary message")
            question = update.message.text
            original_messages = context.chat_data.get('original_messages', [])

            # Generate an answer using GPT
            answer = get_answer_from_gpt(original_messages, question)
            answer = answer.replace(".", "\\.")
            answer = answer.replace("-", "\\-")
            answer = answer.replace("(", "\\(")
            answer = answer.replace(")", "\\)")

            await context.bot.send_message(
                chat_id=chat_id,
                text=answer,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True,
            )
        else:
            logger.info("Message is not a reply to the summary message")
    else:
        logger.info("Message is not a reply to any message")

async def download_tiktok(update: Update, context):
    """Download TikTok video."""
    if not context.args:
        await update.message.reply_text("Please provide a TikTok URL.")
        return

    url = context.args[0]
    chat_id = update.effective_chat.id if update.effective_chat else None

    if chat_id is None:
        await update.message.reply_text("Error: Unable to get chat ID.")
        return

    ydl_opts = {
        'format': 'best',
        'outtmpl': '/tmp/%(id)s.%(ext)s',
        'nocheckcertificate': True,
        'trim_filenames': True,
        'extractor_args': {
            'tiktok': {
                'api_hostname': 'api22-normal-c-useast2a.tiktokv.com'
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

            video_file = ydl.prepare_filename(info_dict)

        logger.info(f"Downloaded TikTok video: {video_file}")
        await context.bot.send_video(chat_id=chat_id, video=open(video_file, 'rb'))
        os.remove(video_file)
    except Exception as e:
        logger.error(e)
        await update.message.reply_text("An error occurred while downloading the video:", e)

async def inline_query(update: Update, context):
    """Handle inline queries."""
    query = update.inline_query.query
    results = [
        InlineQueryResultArticle(
            id=str(uuid4()),
            title="Summarize Conversation",
            input_message_content=InputTextMessageContent(f"/tldr"),
            description="Summarize the conversation in the group chat",
        ),
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
    if BOT_TOKEN is None:
        raise ValueError("BOT_TOKEN environment variable is not set")

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("tldr", summarize_command))
    application.add_handler(CommandHandler("dl", download_tiktok))

    # Register message handler for replies
    application.add_handler(MessageHandler(filters.REPLY, handle_reply))

    # Register inline query handler
    application.add_handler(InlineQueryHandler(inline_query))

    if WEBHOOK_URL:
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=WEBHOOK_URL + BOT_TOKEN,
        )
        logger.info("Application running via webhook: ")
    else:
        application.run_polling()
        logger.info("Application running via polling: ")

if __name__ == "__main__":
    main()
