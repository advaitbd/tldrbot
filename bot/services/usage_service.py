"""
Usage service that combines quota management with premium user logic.
Handles all usage tracking and enforcement for freemium functionality.
"""
import logging
from typing import Dict

from utils.quota_manager import QuotaManager
from utils.user_management import is_premium, get_or_create_user

logger = logging.getLogger(__name__)

class UsageService:
    def __init__(self):
        self.quota_manager = QuotaManager()
    
    async def within_quota(self, telegram_id: int, chat_id: int) -> bool:
        """
        Check if user is within all quotas (premium users bypass all checks).
        
        Args:
            telegram_id: Telegram user ID
            chat_id: Chat ID where command was triggered
            
        Returns:
            True if user can use the bot, False if quota exceeded
        """
        try:
            # Premium users bypass all quota checks
            if is_premium(telegram_id):
                logger.info(f"Premium user {telegram_id} bypassed quota check")
                return True
            
            # For free users, check all quota limits
            return await self.quota_manager.within_quota(telegram_id, chat_id)
            
        except Exception as e:
            logger.error(f"Error in within_quota for {telegram_id}: {e}")
            return False  # Fail-safe: block if error
    
    async def increment_counters(self, telegram_id: int, chat_id: int) -> Dict:
        """
        Increment usage counters for free users (premium users don't need counting).
        
        Args:
            telegram_id: Telegram user ID
            chat_id: Chat ID where command was triggered
            
        Returns:
            Dict with updated counter values
        """
        try:
            # Ensure user exists in database
            get_or_create_user(telegram_id)
            
            # Premium users don't need counter tracking
            if is_premium(telegram_id):
                logger.info(f"Premium user {telegram_id} - skipping counter increment")
                return {'daily': 0, 'monthly': 0, 'groups': 0, 'premium': True}
            
            # Increment counters for free users
            counters = await self.quota_manager.increment_counters(telegram_id, chat_id)
            counters['premium'] = False
            
            logger.info(f"Updated counters for {telegram_id}: {counters}")
            return counters
            
        except Exception as e:
            logger.error(f"Error in increment_counters for {telegram_id}: {e}")
            return {'daily': 999, 'monthly': 999, 'groups': 999, 'premium': False}
    
    async def get_usage_stats(self, telegram_id: int) -> Dict:
        """
        Get comprehensive usage statistics for user.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            Dict with usage stats and limits
        """
        try:
            # Ensure user exists in database
            get_or_create_user(telegram_id)
            
            if is_premium(telegram_id):
                return {
                    'daily': 0,
                    'monthly': 0,
                    'groups': 0,
                    'daily_limit': 'unlimited',
                    'monthly_limit': 'unlimited',
                    'group_limit': 'unlimited',
                    'premium': True
                }
            
            # Get stats for free users
            stats = await self.quota_manager.get_usage_stats(telegram_id)
            stats['premium'] = False
            return stats
            
        except Exception as e:
            logger.error(f"Error in get_usage_stats for {telegram_id}: {e}")
            return {
                'daily': 999,
                'monthly': 999,
                'groups': 999,
                'daily_limit': 5,
                'monthly_limit': 100,
                'group_limit': 3,
                'premium': False
            }
    
    async def format_usage_string(self, telegram_id: int) -> str:
        """
        Format usage statistics as a readable string for bot commands.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            Formatted usage string
        """
        stats = await self.get_usage_stats(telegram_id)
        
        if stats['premium']:
            return "✅ Premium user (unlimited)"
        
        return (f"Today: {stats['daily']}/{stats['daily_limit']} · "
                f"Month: {stats['monthly']}/{stats['monthly_limit']} · "
                f"Groups: {stats['groups']}/{stats['group_limit']} (Free)")
    
    async def clear_premium_user_quotas(self, telegram_id: int) -> bool:
        """
        Clear quota counters when user upgrades to premium.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            True if successful
        """
        try:
            # Clear group tracking (premium users can use unlimited groups)
            await self.quota_manager.clear_user_groups(telegram_id)
            logger.info(f"Cleared quota counters for new premium user {telegram_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing quotas for {telegram_id}: {e}")
            return False
    
    async def health_check(self) -> bool:
        """
        Check if the usage service is healthy (Redis + Database).
        
        Returns:
            True if all systems are operational
        """
        try:
            redis_ok = await self.quota_manager.health_check()
            # Test database by checking if we can create a user
            test_user = get_or_create_user(999999999)  # Test with dummy ID
            db_ok = test_user is not None
            
            return redis_ok and db_ok
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False 