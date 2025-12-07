"""
Plugin system for TLDRBot.
Each plugin is a self-contained module that registers its own handlers.
"""
from abc import ABC, abstractmethod
from telegram.ext import Application
from typing import List, Tuple


class Plugin(ABC):
    """Base class for all plugins."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name for logging."""
        pass
    
    @property
    def commands(self) -> List[Tuple[str, str]]:
        """List of (command, description) tuples for the bot menu.
        Override this if your plugin adds commands."""
        return []
    
    @abstractmethod
    def register(self, app: Application) -> None:
        """Register handlers with the application."""
        pass


# Import plugins for convenience
from plugins.help import HelpPlugin
from plugins.summarize import SummarizePlugin
from plugins.mention_reply import MentionReplyPlugin
from plugins.auto_download import AutoDownloadPlugin

__all__ = [
    'Plugin',
    'HelpPlugin',
    'SummarizePlugin',
    'MentionReplyPlugin',
    'AutoDownloadPlugin',
]

