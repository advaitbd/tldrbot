"""
Unit tests for quota logic and freemium functionality.
Tests quota checking functions, counter increments, premium bypass, and Redis error handling.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from services.usage_service import UsageService
from utils.quota_manager import QuotaManager
from utils.user_management import is_premium, get_or_create_user


class TestQuotaLogic:
    """Test suite for quota checking and enforcement logic."""
    
    @pytest.fixture
    def usage_service(self):
        """Create a UsageService instance for testing."""
        return UsageService()
    
    @pytest.fixture
    def quota_manager(self):
        """Create a QuotaManager instance for testing."""
        return QuotaManager()
    
    @pytest.mark.asyncio
    async def test_within_quota_free_user_under_limit(self, usage_service):
        """Test that free users under quota limits are allowed."""
        user_id = 12345
        chat_id = -67890
        
        # Mock Redis responses for a user under limits
        with patch.object(usage_service.quota_manager, 'get_daily_usage', return_value=3), \
             patch.object(usage_service.quota_manager, 'get_monthly_usage', return_value=50), \
             patch.object(usage_service.quota_manager, 'get_user_group_count', return_value=2), \
             patch('services.usage_service.is_premium', return_value=False):
            
            result = await usage_service.within_quota(user_id, chat_id)
            assert result is True
    
    @pytest.mark.asyncio
    async def test_within_quota_free_user_daily_limit_exceeded(self, usage_service):
        """Test that free users over daily limit are blocked."""
        user_id = 12345
        chat_id = -67890
        
        # Mock Redis responses for a user over daily limit
        with patch.object(usage_service.quota_manager, 'get_daily_usage', return_value=5), \
             patch.object(usage_service.quota_manager, 'get_monthly_usage', return_value=50), \
             patch.object(usage_service.quota_manager, 'get_user_group_count', return_value=2), \
             patch('services.usage_service.is_premium', return_value=False):
            
            result = await usage_service.within_quota(user_id, chat_id)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_within_quota_free_user_monthly_limit_exceeded(self, usage_service):
        """Test that free users over monthly limit are blocked."""
        user_id = 12345
        chat_id = -67890
        
        # Mock Redis responses for a user over monthly limit
        with patch.object(usage_service.quota_manager, 'get_daily_usage', return_value=3), \
             patch.object(usage_service.quota_manager, 'get_monthly_usage', return_value=100), \
             patch.object(usage_service.quota_manager, 'get_user_group_count', return_value=2), \
             patch('services.usage_service.is_premium', return_value=False):
            
            result = await usage_service.within_quota(user_id, chat_id)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_within_quota_free_user_group_limit_exceeded(self, usage_service):
        """Test that free users over group limit are blocked from NEW groups."""
        user_id = 12345
        chat_id = -67890  # New group they're not in yet
        
        # Mock Redis responses for a user already in 3 groups, trying to join a new one
        with patch.object(usage_service.quota_manager, 'get_daily_usage', return_value=3), \
             patch.object(usage_service.quota_manager, 'get_monthly_usage', return_value=50), \
             patch.object(usage_service.quota_manager.redis, 'sismember', return_value=False), \
             patch.object(usage_service.quota_manager.redis, 'scard', return_value=3), \
             patch('services.usage_service.is_premium', return_value=False):
            
            result = await usage_service.within_quota(user_id, chat_id)
            assert result is False  # Should be blocked from joining new group
    
    @pytest.mark.asyncio
    async def test_within_quota_premium_user_bypass(self, usage_service):
        """Test that premium users bypass all quota checks."""
        user_id = 12345
        chat_id = -67890
        
        # Mock Redis responses for a user over all limits, but premium
        with patch.object(usage_service.quota_manager, 'get_daily_usage', return_value=100), \
             patch.object(usage_service.quota_manager, 'get_monthly_usage', return_value=1000), \
             patch.object(usage_service.quota_manager, 'get_user_group_count', return_value=10), \
             patch('services.usage_service.is_premium', return_value=True):
            
            result = await usage_service.within_quota(user_id, chat_id)
            assert result is True
    
    @pytest.mark.asyncio
    async def test_increment_counters_success(self, usage_service):
        """Test successful counter increment."""
        user_id = 12345
        chat_id = -67890
        
        # Mock successful Redis operations
        with patch.object(usage_service.quota_manager, 'increment_daily_usage', return_value=4), \
             patch.object(usage_service.quota_manager, 'increment_monthly_usage', return_value=51), \
             patch.object(usage_service.quota_manager, 'add_user_to_group', return_value=None):
            
            result = await usage_service.increment_counters(user_id, chat_id)
            
            assert 'daily' in result
            assert 'monthly' in result
            assert result['daily'] == 4
            assert result['monthly'] == 51
    
    @pytest.mark.asyncio
    async def test_redis_error_handling_fail_safe(self, usage_service):
        """Test that Redis errors trigger fail-safe blocking for free users."""
        user_id = 12345
        chat_id = -67890
        
        # Mock Redis connection error
        with patch.object(usage_service.quota_manager, 'get_daily_usage', side_effect=Exception("Redis connection failed")), \
             patch('services.usage_service.is_premium', return_value=False):
            
            result = await usage_service.within_quota(user_id, chat_id)
            assert result is False  # Fail-safe: block free users when Redis is down
    
    @pytest.mark.asyncio
    async def test_redis_error_handling_premium_bypass(self, usage_service):
        """Test that Redis errors don't affect premium users."""
        user_id = 12345
        chat_id = -67890
        
        # Mock Redis connection error but user is premium
        with patch.object(usage_service.quota_manager, 'get_daily_usage', side_effect=Exception("Redis connection failed")), \
             patch('services.usage_service.is_premium', return_value=True):
            
            result = await usage_service.within_quota(user_id, chat_id)
            assert result is True  # Premium users should still work when Redis is down
    
    @pytest.mark.asyncio
    async def test_dm_throttling(self, quota_manager):
        """Test DM throttling functionality."""
        user_id = 12345
        
        # Mock Redis operations for DM throttling - use AsyncMock for async methods
        with patch.object(quota_manager.redis, 'exists', new_callable=AsyncMock, return_value=False):
            # First DM should be allowed (no throttle key exists)
            result = await quota_manager.can_send_dm(user_id)
            assert result is True
        
        with patch.object(quota_manager.redis, 'exists', new_callable=AsyncMock, return_value=True):
            # Second DM within 15 minutes should be blocked (throttle key exists)
            result = await quota_manager.can_send_dm(user_id)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_counter_reset_logic(self, quota_manager):
        """Test that counters reset properly at the right times."""
        user_id = 12345
        
        # Test daily counter reset (should use setex with TTL)
        with patch.object(quota_manager.redis, 'get', new_callable=AsyncMock, return_value=None), \
             patch.object(quota_manager, '_set_daily_counter_with_expiry', new_callable=AsyncMock) as mock_set_expiry:
            
            await quota_manager.increment_daily_usage(user_id)
            
            # Verify that _set_daily_counter_with_expiry was called for new counter
            mock_set_expiry.assert_called_once_with(user_id, 1)
    
    def test_quota_limits_constants(self):
        """Test that quota limits match PRD specifications."""
        from utils.quota_manager import DAILY_LIMIT, MONTHLY_LIMIT, GROUP_LIMIT
        
        assert DAILY_LIMIT == 5, "Daily limit should be 5 as per PRD"
        assert MONTHLY_LIMIT == 100, "Monthly limit should be 100 as per PRD"
        assert GROUP_LIMIT == 3, "Group limit should be 3 as per PRD"
    
    @pytest.mark.asyncio
    async def test_usage_statistics_formatting(self, usage_service):
        """Test that usage statistics are formatted correctly."""
        user_id = 12345
        
        # Mock usage data for free user
        with patch.object(usage_service.quota_manager, 'get_daily_usage', return_value=3), \
             patch.object(usage_service.quota_manager, 'get_monthly_usage', return_value=45), \
             patch.object(usage_service.quota_manager, 'get_user_group_count', return_value=2), \
             patch('services.usage_service.is_premium', return_value=False):
            
            result = await usage_service.format_usage_string(user_id)
            
            assert "3/5" in result  # Daily usage
            assert "45/100" in result  # Monthly usage
            assert "2/3" in result  # Group usage
            assert "Free" in result  # Plan type
        
        # Test premium user formatting
        with patch('services.usage_service.is_premium', return_value=True):
            result = await usage_service.format_usage_string(user_id)
            assert "Premium user (unlimited)" in result

    @pytest.mark.asyncio
    async def test_premium_subscription_status_messaging(self, usage_service):
        """Test that premium users see appropriate subscription timing messages."""
        user_id = 12345
        from datetime import datetime, timedelta
        import pytz
        
        future_date = datetime.now(pytz.UTC) + timedelta(days=15)
        
        # Test active premium subscription (not cancelled)
        with patch('services.usage_service.is_premium', return_value=True), \
             patch.object(usage_service, '_get_subscription_status', return_value=(False, future_date)):
            
            result = await usage_service.format_usage_string(user_id)
            
            assert "Premium user (unlimited)" in result
            assert "Next payment due:" in result
            assert future_date.strftime("%B %d, %Y") in result
        
        # Test cancelled premium subscription (access until period end)
        with patch('services.usage_service.is_premium', return_value=True), \
             patch.object(usage_service, '_get_subscription_status', return_value=(True, future_date)):
            
            result = await usage_service.format_usage_string(user_id)
            
            assert "Premium user (unlimited)" in result
            assert "Premium access ends:" in result
            assert future_date.strftime("%B %d, %Y") in result
        
        # Test premium user without subscription timing info (fallback)
        with patch('services.usage_service.is_premium', return_value=True), \
             patch.object(usage_service, '_get_subscription_status', return_value=None):
            
            result = await usage_service.format_usage_string(user_id)
            
            assert result == "✅ Premium user (unlimited)"


if __name__ == "__main__":
    pytest.main([__file__]) 