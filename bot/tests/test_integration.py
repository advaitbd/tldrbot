"""
Integration tests for the freemium functionality.
Tests end-to-end upgrade flow, quota enforcement, and system integration.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from services.usage_service import UsageService
from services.stripe_service import StripeService
from handlers.webhook_handlers import WebhookHandlers
from utils.quota_manager import QuotaManager


class TestFreemiumIntegration:
    """Integration tests for the complete freemium system."""
    
    @pytest.fixture
    def usage_service(self):
        """Create a UsageService instance for testing."""
        return UsageService()
    
    @pytest.fixture
    def stripe_service(self):
        """Create a StripeService instance for testing."""
        return StripeService()
    
    @pytest.fixture
    def quota_manager(self):
        """Create a QuotaManager instance for testing."""
        return QuotaManager()
    
    @pytest.mark.asyncio
    async def test_end_to_end_upgrade_flow(self, usage_service, stripe_service):
        """Test complete user journey from free to premium."""
        user_id = 12345
        chat_id = -67890
        customer_id = "cus_test_customer"
        expires_at = datetime.now() + timedelta(days=30)
        
        # Step 1: Free user hits quota limit
        with patch('services.usage_service.is_premium', return_value=False), \
             patch.object(usage_service.quota_manager, 'get_daily_usage', return_value=5), \
             patch.object(usage_service.quota_manager, 'get_monthly_usage', return_value=50), \
             patch.object(usage_service.quota_manager, 'get_user_group_count', return_value=2):
            
            # User should be blocked (daily limit reached)
            within_quota = await usage_service.within_quota(user_id, chat_id)
            assert within_quota is False
        
        # Step 2: User upgrades to premium
        with patch('utils.user_management.update_premium_status', return_value=True), \
             patch('services.usage_service.UsageService') as mock_usage_service_class:
            
            mock_usage_service = Mock()
            mock_usage_service.clear_premium_user_quotas = AsyncMock()
            mock_usage_service_class.return_value = mock_usage_service
            
            # Activate premium
            success = await stripe_service.activate_premium(user_id, expires_at, customer_id)
            assert success is True
            
            # Verify quota counters were cleared
            mock_usage_service.clear_premium_user_quotas.assert_called_once_with(user_id)
        
        # Step 3: Premium user bypasses all quotas
        with patch('services.usage_service.is_premium', return_value=True):
            # Even with high usage, premium user should be allowed
            within_quota = await usage_service.within_quota(user_id, chat_id)
            assert within_quota is True
    
    @pytest.mark.asyncio
    async def test_quota_enforcement_in_real_bot_environment(self, usage_service):
        """Test quota enforcement as it would work in the real bot."""
        user_id = 12345
        chat_id = -67890
        
        # Mock Redis operations for a user at the daily limit
        with patch('services.usage_service.is_premium', return_value=False), \
             patch.object(usage_service.quota_manager, 'within_quota', return_value=False), \
             patch.object(usage_service.quota_manager, 'get_daily_usage', return_value=5), \
             patch.object(usage_service.quota_manager, 'get_monthly_usage', return_value=50), \
             patch.object(usage_service.quota_manager, 'get_user_group_count', return_value=2):
            
            # Check quota (should be blocked)
            within_quota = await usage_service.within_quota(user_id, chat_id)
            assert within_quota is False
            
            # Get usage stats for display
            stats = await usage_service.get_usage_stats(user_id)
            assert stats['daily'] == 5
            assert stats['monthly'] == 50
            assert stats['groups'] == 2
            assert stats['premium'] is False
            
            # Format usage string
            usage_string = await usage_service.format_usage_string(user_id)
            assert "5/5" in usage_string  # Daily limit reached
            assert "50/100" in usage_string  # Monthly usage
            assert "2/3" in usage_string  # Group usage
            assert "Free" in usage_string
    
    @pytest.mark.asyncio
    async def test_stripe_webhook_integration(self, stripe_service):
        """Test Stripe webhook integration with proper data flow."""
        telegram_id = 123456789
        customer_id = "cus_test_customer"
        
        # Mock successful webhook processing
        webhook_data = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_session",
                    "customer": customer_id,
                    "subscription": "sub_test_subscription",
                    "client_reference_id": str(telegram_id)
                }
            }
        }
        
        # Mock Stripe subscription retrieval
        mock_subscription = Mock()
        mock_subscription.__getitem__ = Mock(side_effect=lambda key: {
            'items': Mock(data=[Mock(current_period_end=1234567890)])
        }[key])
        
        with patch('stripe.Subscription.retrieve', return_value=mock_subscription), \
             patch('utils.user_management.update_premium_status', return_value=True), \
             patch('services.usage_service.UsageService') as mock_usage_service_class, \
             patch('stripe.Customer.modify'):  # Mock customer metadata update
            
            mock_usage_service = Mock()
            mock_usage_service.clear_premium_user_quotas = AsyncMock()
            mock_usage_service_class.return_value = mock_usage_service
            
            # Process webhook
            result = await stripe_service.handle_checkout_completed(webhook_data)
            
            # Verify successful processing
            assert result is True
    
    @pytest.mark.asyncio
    async def test_redis_and_database_integration(self, usage_service):
        """Test Redis and database integration for quota management."""
        user_id = 12345
        
        # Test health check functionality
        with patch.object(usage_service.quota_manager, 'health_check', return_value=True), \
             patch('utils.user_management.get_or_create_user', return_value=Mock()):
            
            health_ok = await usage_service.health_check()
            assert health_ok is True
        
        # Test error scenarios
        with patch.object(usage_service.quota_manager, 'health_check', return_value=False):
            health_ok = await usage_service.health_check()
            assert health_ok is False
    
    @pytest.mark.asyncio
    async def test_error_scenarios_and_recovery(self, usage_service):
        """Test error scenarios and system recovery."""
        user_id = 12345
        chat_id = -67890
        
        # Test Redis failure scenario
        with patch('services.usage_service.is_premium', return_value=False), \
             patch.object(usage_service.quota_manager, 'within_quota', side_effect=Exception("Redis connection failed")):
            
            # Should fail-safe to blocking free users
            within_quota = await usage_service.within_quota(user_id, chat_id)
            assert within_quota is False
        
        # Test premium user still works during Redis failure
        with patch('services.usage_service.is_premium', return_value=True), \
             patch.object(usage_service.quota_manager, 'within_quota', side_effect=Exception("Redis connection failed")):
            
            # Premium users should still work
            within_quota = await usage_service.within_quota(user_id, chat_id)
            assert within_quota is True
    
    @pytest.mark.asyncio
    async def test_performance_quota_checking(self, usage_service):
        """Test that quota checking is fast enough for production use."""
        user_id = 12345
        chat_id = -67890
        
        # Mock fast Redis responses
        with patch('services.usage_service.is_premium', return_value=False), \
             patch.object(usage_service.quota_manager, 'within_quota', return_value=True):
            
            import time
            start_time = time.time()
            
            # Run quota check
            result = await usage_service.within_quota(user_id, chat_id)
            
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            
            # Should complete quickly (under 50ms as per PRD)
            assert duration_ms < 50
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__]) 