# bot/utils/memory_storage.py
from collections import defaultdict, deque
from typing import List

"""
Note: This uses an in-memory approach, so when you restart your bot, all data is lost.
If you want persistence, store messages in a database (SQLite, PostgreSQL, etc.) using an ORM or direct queries.
"""

class MemoryStorage:
    def __init__(self, max_messages: int = 400):
        """
        max_messages indicates how many messages we keep per chat.
        """
        self.storage = defaultdict(lambda: deque(maxlen=max_messages))

    def store_message(self, chat_id: int, sender_name: str, message_text: str):
        """
        Store a single message for a particular chat.
        """
        self.storage[chat_id].append(f"{sender_name}: {message_text}")

    def get_recent_messages(self, chat_id: int, num_messages: int) -> List[str]:
        """
        Return up to the last 'num_messages' messages for chat_id.
        If there are fewer than num_messages stored, return all of them.
        """
        messages = self.storage[chat_id]
        # Return the LAST num_messages as a list
        return list(messages)[-num_messages:]
