"""Auto-download plugin for video URLs."""
import re
import os
import logging
import asyncio
import random
import yt_dlp
from telegram import Update, Message
from telegram.ext import Application, MessageHandler, ContextTypes, filters
from plugins import Plugin
from config import VIDEO_URL_PATTERNS

logger = logging.getLogger(__name__)

URL_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in VIDEO_URL_PATTERNS]

PROCESSING_MESSAGES = [
    "⏳ Spotted a video link! Fetching it for you...",
    "⏳ Video detected! Let me grab that...",
    "⏳ Hold on, downloading your video...",
    "⏳ I see you found something. Downloading...",
    "⏳ Video link detected. Working on it...",
]

SUCCESS_MESSAGES = [
    "🎬 Detected your TikTok addiction. Here's the video.",
    "🎬 I see you found something worth sharing. Here it is.",
    "🎬 Another video? Fine, I'll fetch it. You're welcome.",
    "🎬 Your wish is my command. Unfortunately.",
    "🎬 Downloaded. Try not to spend all day watching these.",
]

ERROR_MESSAGES = [
    "😅 I tried to download that video but it didn't work. Maybe the link is broken?",
    "🤷 Couldn't fetch that video. The internet gremlins got it.",
    "😬 Download failed. Maybe try a different link?",
    "💀 That video didn't want to be downloaded. Can't blame it.",
]


class AutoDownloadPlugin(Plugin):
    def __init__(self):
        self._download_queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
    
    @property
    def name(self) -> str:
        return "auto_download"
    
    def register(self, app: Application) -> None:
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.check_for_urls
        ), group=2)
        app.post_init = self._start_worker
        app.post_shutdown = self._stop_worker
    
    async def _start_worker(self, app: Application) -> None:
        self._worker_task = asyncio.create_task(self._download_worker(app))
        logger.info("Download worker started")
    
    async def _stop_worker(self, app: Application) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("Download worker stopped")
    
    def _extract_video_url(self, text: str) -> str | None:
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, text)
        
        for url in urls:
            for pattern in URL_PATTERNS:
                if pattern.search(url):
                    return url
        return None
    
    async def check_for_urls(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text:
            return
        url = self._extract_video_url(update.message.text)
        if not url:
            return
        chat_id = update.effective_chat.id if update.effective_chat else None
        if not chat_id:
            return
        
        logger.info(f"Video URL detected: {url}")
        status_msg = await update.message.reply_text(random.choice(PROCESSING_MESSAGES))
        
        job = {
            "url": url,
            "chat_id": chat_id,
            "reply_to_message_id": update.message.message_id,
            "status_message": status_msg,
            "bot": context.bot,
        }
        await self._download_queue.put(job)
        logger.info(f"Download job queued for {url}")
    
    async def _download_worker(self, app: Application) -> None:
        while True:
            try:
                job = await self._download_queue.get()
                url = job["url"]
                chat_id = job["chat_id"]
                reply_to = job["reply_to_message_id"]
                status_msg: Message = job["status_message"]
                bot = job["bot"]
                
                logger.info(f"Processing download: {url}")
                try:
                    await status_msg.edit_text("⏳ Downloading... This might take a moment.")
                except Exception:
                    pass
                
                video_path = await self._download_video(url)
                
                if video_path and os.path.exists(video_path):
                    try:
                        await status_msg.delete()
                    except Exception:
                        pass
                    
                    try:
                        with open(video_path, 'rb') as video_file:
                            await bot.send_video(
                                chat_id=chat_id, video=video_file,
                                caption=random.choice(SUCCESS_MESSAGES),
                                reply_to_message_id=reply_to
                            )
                        logger.info(f"Video sent for {url}")
                    except Exception as e:
                        logger.error(f"Failed to send video: {e}")
                        await bot.send_message(
                            chat_id=chat_id, reply_to_message_id=reply_to,
                            text="😬 Downloaded but couldn't send. File might be too large."
                        )
                    
                    try:
                        os.remove(video_path)
                    except Exception:
                        pass
                else:
                    error_text = random.choice(ERROR_MESSAGES)
                    try:
                        await status_msg.edit_text(error_text)
                    except Exception:
                        await bot.send_message(chat_id=chat_id, text=error_text, reply_to_message_id=reply_to)
                
                self._download_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Download worker error: {e}")
                await asyncio.sleep(1)
    
    async def _download_video(self, url: str) -> str | None:
        ydl_opts = {
            'format': 'best[filesize<50M]/best',
            'outtmpl': '/tmp/%(id)s.%(ext)s',
            'nocheckcertificate': True,
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {
                'tiktok': {
                    'api_hostname': 'api22-normal-c-useast2a.tiktokv.com'
                }
            }
        }
        
        try:
            loop = asyncio.get_event_loop()
            def download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=True)
                    return ydl.prepare_filename(info_dict)
            return await loop.run_in_executor(None, download)
        except Exception as e:
            logger.error(f"yt-dlp error for {url}: {e}")
            return None
