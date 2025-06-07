"""
Usage service that combines quota management with premium user logic.
Handles all usage tracking and enforcement for freemium functionality.
"""
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple
import pytz
import stripe
import asyncio

from config.settings import StripeConfig
from utils.quota_manager import QuotaManager
from utils.user_management import is_premium, get_or_create_user, check_premium_expiry
from utils.analytics_storage import SessionLocal, User

logger = logging.getLogger(__name__)

# Configure Stripe
if StripeConfig.API_KEY:
    stripe.api_key = StripeConfig.API_KEY

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
            await asyncio.get_running_loop().run_in_executor(None, get_or_create_user, telegram_id)
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
            await asyncio.get_running_loop().run_in_executor(None, get_or_create_user, telegram_id)
            
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
            Formatted usage string with subscription timing information
        """
        stats = await self.get_usage_stats(telegram_id)
        
        if stats['premium']:
            # Get detailed subscription status for premium users
            subscription_info = await self._get_subscription_status(telegram_id)
            
            if subscription_info:
                is_cancelled, expires_date = subscription_info
                if expires_date:
                    formatted_date = expires_date.strftime("%B %d, %Y")
                    
                    if is_cancelled:
                        return f"✅ Premium user (unlimited)\n📅 Premium access ends: {formatted_date}"
                    else:
                        return f"✅ Premium user (unlimited)\n📅 Next payment due: {formatted_date}"
                else:
                    return "✅ Premium user (unlimited)"
            else:
                return "✅ Premium user (unlimited)"
        
        return (f"Today: {stats['daily']}/{stats['daily_limit']} · "
                f"Month: {stats['monthly']}/{stats['monthly_limit']} · "
                f"Groups: {stats['groups']}/{stats['group_limit']} (Free)")
    
    async def _get_subscription_status(self, telegram_id: int) -> Optional[Tuple[bool, Optional[datetime]]]:
        """
        Get subscription status for a premium user.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            Tuple of (is_cancelled, expires_date) or None if error/not found
        """
        try:
            # Get user from database (run in thread pool to avoid blocking)
            user_data = await asyncio.get_event_loop().run_in_executor(
                None, self._get_user_from_db, telegram_id
            )
            
            if not user_data:
                return None
            
            expires_at, stripe_customer_id = user_data
            
            # Check Stripe for cancellation status (run in thread pool to avoid blocking)
            is_cancelled, updated_expires_at = await asyncio.get_event_loop().run_in_executor(
                None, self._check_stripe_subscription_status, stripe_customer_id, expires_at
            )
            
            # Use updated expires_at from Stripe if we got one
            final_expires_at = updated_expires_at if updated_expires_at else expires_at
            
            return (is_cancelled, final_expires_at)
            
        except Exception as e:
            logger.error(f"Error getting subscription status for {telegram_id}: {e}")
            return None
    
    def _get_user_from_db(self, telegram_id: int) -> Optional[Tuple[Optional[datetime], str]]:
        """
        Synchronous helper to get user data from database.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            Tuple of (expires_at, stripe_customer_id) or None if not found
        """
        try:
            with SessionLocal() as session:
                user = session.query(User).filter_by(telegram_id=telegram_id).first()
                
                if not user or not user.premium or not user.stripe_customer_id:
                    return None
                
                return (user.premium_expires_at, user.stripe_customer_id)
                
        except Exception as e:
            logger.error(f"Database error getting user {telegram_id}: {e}")
            return None
    
    def _check_stripe_subscription_status(self, stripe_customer_id: str, db_expires_at: Optional[datetime]) -> Tuple[bool, Optional[datetime]]:
        """
        Synchronous helper to check Stripe subscription status.
        
        Args:
            stripe_customer_id: Stripe customer ID
            db_expires_at: Expiry date from database
            
        Returns:
            Tuple of (is_cancelled, expires_at)
        """
        is_cancelled = False
        expires_at = db_expires_at
        
        try:
            # Find active subscription
            subscriptions = stripe.Subscription.list(
                customer=stripe_customer_id,
                status='active',
                limit=1
            )
            
            if subscriptions.data:
                subscription = subscriptions.data[0]
                is_cancelled = subscription.get('cancel_at_period_end', False)
                
                # If we don't have expires_at in DB, get it from Stripe
                if not expires_at and subscription.get('current_period_end'):
                    expires_at = datetime.fromtimestamp(
                        subscription['current_period_end'], 
                        tz=pytz.UTC
                    )
                    
        except Exception as e:
            logger.warning(f"Could not fetch Stripe subscription status for customer {stripe_customer_id}: {e}")
            # Continue with database info only
        
        return (is_cancelled, expires_at)
    
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
            test_user = await asyncio.get_running_loop().run_in_executor(None, get_or_create_user, 999999999)  # Test with dummy ID
            db_ok = test_user is not None
            
            return redis_ok and db_ok
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False 