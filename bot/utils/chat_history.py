from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from typing import List
from config.settings import TelegramConfig, CensorConfig

class ChatHistoryManager:
    def __init__(self):
        self.client = TelegramClient(
            StringSession(TelegramConfig.STRING),
            TelegramConfig.API_ID,
            TelegramConfig.API_HASH
        )

    async def get_chat_history(self, chat_id: int, num_messages: int) -> str:
        await self.client.start()
        try:
            messages = await self.client.get_messages(chat_id, limit=num_messages)
            result = self._format_messages(messages)
            censored_result = self._censor_messages(result)
            filtered_result = self._filter_bot_messages(censored_result)
            filtered_result.reverse()
            
            return "\n".join(filtered_result)
        finally:
            await self.client.disconnect()

    @staticmethod
    def _format_messages(messages) -> List[str]:
        return [
            f"{message.sender.first_name}: {message.message} \n"
            for message in messages
            if not message.action
        ]

    @staticmethod
    def _filter_bot_messages(messages: List[str]) -> List[str]:
        return [msg for msg in messages if not msg.startswith("tldrbot:")]

    def _censor_messages(self, messages: List[str]) -> List[str]:
        censored = []
        for message in messages:
            words = message.split()
            censored_words = [
                "[REDACTED]" if self._should_censor(word) else word
                for word in words
            ]
            censored.append(" ".join(censored_words))
        return censored

    @staticmethod
    def _should_censor(word: str) -> bool:
        word_lower = word.lower()
        for censor_word in CensorConfig.WORDS.split(","):
            if (word_lower == censor_word or 
                (len(word_lower) >= 4 and (
                    word_lower in censor_word or 
                    censor_word in word_lower
                ))
            ):
                return True
        return False