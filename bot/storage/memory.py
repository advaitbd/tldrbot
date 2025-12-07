"""In-memory message storage for chat history."""
from collections import defaultdict, deque
from typing import List, Dict, Any


class MemoryStorage:
    def __init__(self, max_messages: int = 400):
        self.max_messages = max_messages
        self._messages: Dict[int, deque] = defaultdict(lambda: deque(maxlen=max_messages))
        self._summary_context: Dict[int, Dict[str, Any]] = {}
    
    def store_message(self, chat_id: int, sender_name: str, message_text: str) -> None:
        self._messages[chat_id].append(f"{sender_name}: {message_text}")
    
    def get_recent_messages(self, chat_id: int, num_messages: int) -> List[str]:
        return list(self._messages[chat_id])[-num_messages:]
    
    def set_summary_context(self, chat_id: int, summary_message_id: int, original_messages: List[str]) -> None:
        self._summary_context[chat_id] = {
            "summary_message_id": summary_message_id,
            "original_messages": original_messages,
        }
    
    def get_summary_context(self, chat_id: int) -> Dict[str, Any] | None:
        return self._summary_context.get(chat_id)
    
    def clear_chat(self, chat_id: int) -> None:
        if chat_id in self._messages:
            self._messages[chat_id].clear()
        if chat_id in self._summary_context:
            del self._summary_context[chat_id]

