"""Per-user daily rate limiter."""
from datetime import datetime, timezone
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, max_uses_per_day: int = 10):
        self.max_uses_per_day = max_uses_per_day
        self._usage: Dict[int, Dict] = {}
    
    def _get_today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    def _reset_if_new_day(self, user_id: int) -> None:
        today = self._get_today()
        if user_id not in self._usage or self._usage[user_id].get("date") != today:
            self._usage[user_id] = {"count": 0, "date": today}
    
    def can_use(self, user_id: int) -> bool:
        self._reset_if_new_day(user_id)
        return self._usage[user_id]["count"] < self.max_uses_per_day
    
    def record_use(self, user_id: int) -> None:
        self._reset_if_new_day(user_id)
        self._usage[user_id]["count"] += 1
    
    def remaining(self, user_id: int) -> int:
        self._reset_if_new_day(user_id)
        return self.max_uses_per_day - self._usage[user_id]["count"]
    
    def get_limit_message(self) -> str:
        return (
            "🛑 Whoa there, chatty! You've used me 10 times today. "
            "I need a break from your neediness. Try again tomorrow."
        )

