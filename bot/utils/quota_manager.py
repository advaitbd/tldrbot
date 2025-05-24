"""
Redis-based quota management for freemium functionality.
Handles daily/monthly usage tracking, group limits, and DM throttling.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Set
import pytz

import redis.asyncio as redis
from config.settings import RedisConfig

logger = logging.getLogger(__name__)

# Singapore timezone for resets
SINGAPORE_TZ = pytz.timezone('Asia/Singapore')

# Quota limits for free users
DAILY_LIMIT = 5
MONTHLY_LIMIT = 100
GROUP_LIMIT = 3

class QuotaManager:
    def __init__(self):
        self.redis = redis.from_url(RedisConfig.URL)
    
    async def get_daily_usage(self, telegram_id: int) -> int:
        """Get current daily usage count for user."""
        try:
            key = f"usage:daily:{telegram_id}"
            count = await self.redis.get(key)
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"Redis error in get_daily_usage for {telegram_id}: {e}")
            return DAILY_LIMIT  # Fail-safe: assume limit reached
    
    async def get_monthly_usage(self, telegram_id: int) -> int:
        """Get current monthly usage count for user."""
        try:
            key = f"usage:monthly:{telegram_id}"
            count = await self.redis.get(key)
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"Redis error in get_monthly_usage for {telegram_id}: {e}")
            return MONTHLY_LIMIT  # Fail-safe: assume limit reached
    
    async def get_user_group_count(self, telegram_id: int) -> int:
        """Get number of groups user is active in."""
        try:
            key = f"groups:{telegram_id}"
            count = await self.redis.scard(key)
            return count if count else 0
        except Exception as e:
            logger.error(f"Redis error in get_user_group_count for {telegram_id}: {e}")
            return GROUP_LIMIT  # Fail-safe: assume limit reached
    
    async def increment_daily_usage(self, telegram_id: int) -> int:
        """Increment daily usage counter and return new count."""
        try:
            key = f"usage:daily:{telegram_id}"
            
            # Get current count
            current = await self.redis.get(key)
            if current is None:
                # First usage today - set with expiry at next midnight Singapore time
                await self._set_daily_counter_with_expiry(telegram_id, 1)
                return 1
            else:
                # Increment existing counter
                new_count = await self.redis.incr(key)
                return new_count
                
        except Exception as e:
            logger.error(f"Redis error in increment_daily_usage for {telegram_id}: {e}")
            return DAILY_LIMIT  # Fail-safe: assume limit reached
    
    async def increment_monthly_usage(self, telegram_id: int) -> int:
        """Increment monthly usage counter and return new count."""
        try:
            key = f"usage:monthly:{telegram_id}"
            
            # Get current count
            current = await self.redis.get(key)
            if current is None:
                # First usage this month - set with expiry at next month
                await self._set_monthly_counter_with_expiry(telegram_id, 1)
                return 1
            else:
                # Increment existing counter
                new_count = await self.redis.incr(key)
                return new_count
                
        except Exception as e:
            logger.error(f"Redis error in increment_monthly_usage for {telegram_id}: {e}")
            return MONTHLY_LIMIT  # Fail-safe: assume limit reached
    
    async def add_user_to_group(self, telegram_id: int, chat_id: int) -> int:
        """Add user to group tracking and return group count."""
        try:
            key = f"groups:{telegram_id}"
            await self.redis.sadd(key, chat_id)
            count = await self.redis.scard(key)
            return count
        except Exception as e:
            logger.error(f"Redis error in add_user_to_group for {telegram_id}: {e}")
            return GROUP_LIMIT  # Fail-safe: assume limit reached
    
    async def clear_user_groups(self, telegram_id: int) -> bool:
        """Clear all group tracking for user (used when downgrading)."""
        try:
            key = f"groups:{telegram_id}"
            await self.redis.delete(key)
            logger.info(f"Cleared group tracking for user {telegram_id}")
            return True
        except Exception as e:
            logger.error(f"Redis error in clear_user_groups for {telegram_id}: {e}")
            return False
    
    async def can_send_dm(self, telegram_id: int) -> bool:
        """Check if we can send DM to user (not throttled)."""
        try:
            key = f"dm_throttle:{telegram_id}"
            exists = await self.redis.exists(key)
            return not exists
        except Exception as e:
            logger.error(f"Redis error in can_send_dm for {telegram_id}: {e}")
            return False  # Fail-safe: don't send DM if Redis error
    
    async def mark_dm_sent(self, telegram_id: int) -> bool:
        """Mark that DM was sent to user (sets 15min throttle)."""
        try:
            key = f"dm_throttle:{telegram_id}"
            await self.redis.setex(key, 15 * 60, 1)  # 15 minutes
            logger.info(f"Set DM throttle for user {telegram_id}")
            return True
        except Exception as e:
            logger.error(f"Redis error in mark_dm_sent for {telegram_id}: {e}")
            return False
    
    async def within_daily_quota(self, telegram_id: int) -> bool:
        """Check if user is within daily quota."""
        usage = await self.get_daily_usage(telegram_id)
        return usage < DAILY_LIMIT
    
    async def within_monthly_quota(self, telegram_id: int) -> bool:
        """Check if user is within monthly quota."""
        usage = await self.get_monthly_usage(telegram_id)
        return usage < MONTHLY_LIMIT
    
    async def within_group_quota(self, telegram_id: int, chat_id: int) -> bool:
        """Check if user is within group quota for this specific group."""
        try:
            key = f"groups:{telegram_id}"
            
            # Check if user is already in this group
            is_member = await self.redis.sismember(key, chat_id)
            if is_member:
                return True  # Already in group, so it's allowed
            
            # Check if adding this group would exceed limit
            count = await self.redis.scard(key)
            return count < GROUP_LIMIT
            
        except Exception as e:
            logger.error(f"Redis error in within_group_quota for {telegram_id}: {e}")
            return False  # Fail-safe: assume quota exceeded
    
    async def within_quota(self, telegram_id: int, chat_id: int) -> bool:
        """Check if user is within all quotas (daily, monthly, group)."""
        daily_ok = await self.within_daily_quota(telegram_id)
        monthly_ok = await self.within_monthly_quota(telegram_id)
        group_ok = await self.within_group_quota(telegram_id, chat_id)
        
        return daily_ok and monthly_ok and group_ok
    
    async def increment_counters(self, telegram_id: int, chat_id: int) -> dict:
        """Increment all relevant counters and return updated counts."""
        daily_count = await self.increment_daily_usage(telegram_id)
        monthly_count = await self.increment_monthly_usage(telegram_id)
        group_count = await self.add_user_to_group(telegram_id, chat_id)
        
        return {
            'daily': daily_count,
            'monthly': monthly_count,
            'groups': group_count
        }
    
    async def get_usage_stats(self, telegram_id: int) -> dict:
        """Get comprehensive usage statistics for user."""
        daily = await self.get_daily_usage(telegram_id)
        monthly = await self.get_monthly_usage(telegram_id)
        groups = await self.get_user_group_count(telegram_id)
        
        return {
            'daily': daily,
            'monthly': monthly,
            'groups': groups,
            'daily_limit': DAILY_LIMIT,
            'monthly_limit': MONTHLY_LIMIT,
            'group_limit': GROUP_LIMIT
        }
    
    async def _set_daily_counter_with_expiry(self, telegram_id: int, value: int):
        """Set daily counter with expiry at next midnight Singapore time."""
        key = f"usage:daily:{telegram_id}"
        
        # Calculate seconds until next midnight in Singapore
        sg_now = datetime.now(SINGAPORE_TZ)
        next_midnight = (sg_now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        seconds_until_midnight = int((next_midnight - sg_now).total_seconds())
        
        await self.redis.setex(key, seconds_until_midnight, value)
    
    async def _set_monthly_counter_with_expiry(self, telegram_id: int, value: int):
        """Set monthly counter with expiry at next month."""
        key = f"usage:monthly:{telegram_id}"
        
        # Calculate seconds until first day of next month at 00:05 Singapore time
        sg_now = datetime.now(SINGAPORE_TZ)
        if sg_now.month == 12:
            next_month = sg_now.replace(year=sg_now.year + 1, month=1, day=1, hour=0, minute=5, second=0, microsecond=0)
        else:
            next_month = sg_now.replace(month=sg_now.month + 1, day=1, hour=0, minute=5, second=0, microsecond=0)
        
        seconds_until_reset = int((next_month - sg_now).total_seconds())
        await self.redis.setex(key, seconds_until_reset, value)
    
    async def health_check(self) -> bool:
        """Check if Redis connection is healthy."""
        try:
            await self.redis.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False 