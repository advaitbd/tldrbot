"""Bot orchestration."""
import logging
from telegram import BotCommand
from telegram.ext import Application, ApplicationBuilder
from typing import List, Callable, Awaitable, TYPE_CHECKING

if TYPE_CHECKING:
    from plugins import Plugin

logger = logging.getLogger(__name__)


class TLDRBot:
    def __init__(self, token: str):
        self.token = token
        self.application: Application | None = None
        self._plugins: List['Plugin'] = []
        self._post_init_callbacks: List[Callable[[Application], Awaitable[None]]] = []
    
    def register_plugin(self, plugin: 'Plugin') -> None:
        self._plugins.append(plugin)
        logger.info(f"Registered plugin: {plugin.name}")
    
    def setup(self) -> Application:
        self.application = ApplicationBuilder().token(self.token).build()
        original_post_init = None
        
        for plugin in self._plugins:
            plugin.register(self.application)
            
            if self.application.post_init and self.application.post_init != original_post_init:
                self._post_init_callbacks.append(self.application.post_init)
                original_post_init = self.application.post_init
            logger.info(f"Plugin '{plugin.name}' handlers registered")
        
        self._post_init_callbacks.append(self._setup_commands)
        self.application.post_init = self._run_all_post_init
        
        return self.application
    
    async def _run_all_post_init(self, application: Application) -> None:
        for callback in self._post_init_callbacks:
            await callback(application)
    
    async def _setup_commands(self, application: Application) -> None:
        commands = []
        for plugin in self._plugins:
            for cmd, description in plugin.commands:
                commands.append(BotCommand(cmd, description))
        
        if commands:
            await application.bot.set_my_commands(commands)
            logger.info(f"Registered {len(commands)} bot commands")
    
    def run_polling(self) -> None:
        if not self.application:
            self.setup()
        logger.info("Starting bot in polling mode...")
        self.application.run_polling()  # type: ignore[union-attr]
    
    def run_webhook(self, listen: str, port: int, url_path: str, webhook_url: str) -> None:
        if not self.application:
            self.setup()
        logger.info(f"Starting bot in webhook mode on port {port}...")
        self.application.run_webhook(listen=listen, port=port, url_path=url_path, webhook_url=webhook_url)  # type: ignore[union-attr]
