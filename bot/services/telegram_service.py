import yt_dlp
import os
import logging
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

class TelegramService:
    @staticmethod
    async def download_tiktok(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Please provide a TikTok URL.")
            return

        url = context.args[0]
        chat_id = update.effective_chat.id

        try:
            video_path = await TelegramService._download_video(url)
            if video_path:
                await context.bot.send_video(
                chat_id=chat_id,
                    video=open(video_path, 'rb')
                )
                os.remove(video_path)
        except Exception as e:
            logger.error(f"TikTok download error: {e}")
            await update.message.reply_text(f"An error occurred: {str(e)}")

    @staticmethod
    async def _download_video(url: str) -> Optional[str]:
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

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info_dict)
