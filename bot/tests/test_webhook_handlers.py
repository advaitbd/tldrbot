"""
Unit tests for Stripe webhook handlers.
Tests webhook signature verification, premium activation/deactivation, error handling, and database updates.
"""

import pytest
import json
import hmac
import hashlib
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from services.stripe_service import StripeService
from handlers.webhook_handlers import WebhookHandlers


class TestWebhookHandlers:
    """Test suite for Stripe webhook handling."""
    
    @pytest.fixture
    def stripe_service(self):
        """Create a StripeService instance for testing."""
        return StripeService()
    
    @pytest.fixture
    def webhook_handlers(self):
        """Create a WebhookHandlers instance for testing."""
        mock_application = Mock()
        return WebhookHandlers(mock_application)
    
    @pytest.fixture
    def sample_webhook_payload(self):
        """Sample webhook payload for testing."""
        return {
            "id": "evt_test_webhook",
            "object": "event",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_session",
                    "customer": "cus_test_customer",
                    "metadata": {
                        "telegram_id": "123456789"
                    },
                    "subscription": "sub_test_subscription"
                }
            }
        }
    
    def test_webhook_signature_verification_valid(self, stripe_service):
        """Test that valid webhook signatures are accepted."""
        payload = '{"test": "data"}'
        secret = "whsec_test_secret"
        
        # Create valid signature
        signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        sig_header = f"t=1234567890,v1={signature}"
        
        with patch('config.settings.StripeConfig.WEBHOOK_SECRET', secret):
            result = stripe_service.verify_webhook_signature(payload, sig_header)
            assert result is True
    
    def test_webhook_signature_verification_invalid(self, stripe_service):
        """Test that invalid webhook signatures are rejected."""
        payload = '{"test": "data"}'
        secret = "whsec_test_secret"
        invalid_signature = "invalid_signature"
        sig_header = f"t=1234567890,v1={invalid_signature}"
        
        with patch('config.settings.StripeConfig.WEBHOOK_SECRET', secret):
            result = stripe_service.verify_webhook_signature(payload, sig_header)
            assert result is False
    
    def test_webhook_signature_verification_missing_secret(self, stripe_service):
        """Test webhook verification when secret is missing."""
        payload = '{"test": "data"}'
        sig_header = "t=1234567890,v1=signature"
        
        with patch('config.settings.StripeConfig.WEBHOOK_SECRET', None):
            result = stripe_service.verify_webhook_signature(payload, sig_header)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_checkout_session_completed_handler(self, stripe_service, sample_webhook_payload):
        """Test successful checkout session completion handling."""
        telegram_id = 123456789
        customer_id = "cus_test_customer"
        
        with patch('utils.user_management.get_or_create_user') as mock_get_user, \
             patch('utils.user_management.update_premium_status') as mock_update_premium, \
             patch.object(stripe_service, 'send_premium_welcome_message') as mock_send_welcome:
            
            mock_get_user.return_value = Mock()
            
            await stripe_service.handle_checkout_completed(sample_webhook_payload['data']['object'])
            
            # Verify user was created/retrieved
            mock_get_user.assert_called_once_with(telegram_id)
            
            # Verify premium status was updated
            mock_update_premium.assert_called_once()
            args = mock_update_premium.call_args[0]
            assert args[0] == telegram_id  # telegram_id
            assert args[1] is True  # premium status
            assert args[2] is not None  # expires_at
            assert args[3] == customer_id  # stripe_customer_id
            
            # Verify welcome message was sent
            mock_send_welcome.assert_called_once_with(telegram_id)
    
    @pytest.mark.asyncio
    async def test_subscription_updated_renewal(self, stripe_service):
        """Test subscription renewal handling."""
        subscription_data = {
            "id": "sub_test",
            "customer": "cus_test_customer",
            "status": "active",
            "current_period_end": 1234567890,
            "metadata": {
                "telegram_id": "123456789"
            }
        }
        
        with patch('utils.user_management.update_premium_status') as mock_update_premium, \
             patch.object(stripe_service, 'send_renewal_notification') as mock_send_renewal:
            
            await stripe_service.handle_subscription_updated(subscription_data)
            
            # Verify premium status was updated with new expiry
            mock_update_premium.assert_called_once()
            args = mock_update_premium.call_args[0]
            assert args[0] == 123456789  # telegram_id
            assert args[1] is True  # premium status
            
            # Verify renewal notification was sent
            mock_send_renewal.assert_called_once_with(123456789)
    
    @pytest.mark.asyncio
    async def test_subscription_updated_cancellation(self, stripe_service):
        """Test subscription cancellation handling."""
        subscription_data = {
            "id": "sub_test",
            "customer": "cus_test_customer",
            "status": "canceled",
            "metadata": {
                "telegram_id": "123456789"
            }
        }
        
        with patch('utils.user_management.update_premium_status') as mock_update_premium, \
             patch.object(stripe_service, 'send_cancellation_notification') as mock_send_cancellation:
            
            await stripe_service.handle_subscription_updated(subscription_data)
            
            # Verify premium status was deactivated
            mock_update_premium.assert_called_once()
            args = mock_update_premium.call_args[0]
            assert args[0] == 123456789  # telegram_id
            assert args[1] is False  # premium status (deactivated)
            
            # Verify cancellation notification was sent
            mock_send_cancellation.assert_called_once_with(123456789)
    
    @pytest.mark.asyncio
    async def test_premium_activation_redis_cleanup(self, stripe_service):
        """Test that premium activation clears Redis quota counters."""
        telegram_id = 123456789
        expires_at = "2024-12-31T23:59:59Z"
        customer_id = "cus_test_customer"
        
        with patch('utils.user_management.update_premium_status') as mock_update_premium, \
             patch('services.quota_manager.QuotaManager') as mock_quota_manager_class:
            
            mock_quota_manager = Mock()
            mock_quota_manager_class.return_value = mock_quota_manager
            mock_quota_manager.clear_user_quotas = AsyncMock()
            
            await stripe_service.activate_premium(telegram_id, expires_at, customer_id)
            
            # Verify quota counters were cleared
            mock_quota_manager.clear_user_quotas.assert_called_once_with(telegram_id)
    
    @pytest.mark.asyncio
    async def test_premium_deactivation_redis_cleanup(self, stripe_service):
        """Test that premium deactivation clears premium-related Redis keys."""
        telegram_id = 123456789
        
        with patch('utils.user_management.update_premium_status') as mock_update_premium, \
             patch('services.quota_manager.QuotaManager') as mock_quota_manager_class:
            
            mock_quota_manager = Mock()
            mock_quota_manager_class.return_value = mock_quota_manager
            mock_quota_manager.clear_user_quotas = AsyncMock()
            
            await stripe_service.deactivate_premium(telegram_id)
            
            # Verify quota counters were cleared (reset to free tier)
            mock_quota_manager.clear_user_quotas.assert_called_once_with(telegram_id)
    
    @pytest.mark.asyncio
    async def test_webhook_error_handling_database_failure(self, stripe_service, sample_webhook_payload):
        """Test webhook error handling when database operations fail."""
        with patch('utils.user_management.get_or_create_user', side_effect=Exception("Database error")), \
             patch('logging.Logger.error') as mock_logger:
            
            # Should not raise exception, but should log error
            await stripe_service.handle_checkout_completed(sample_webhook_payload['data']['object'])
            
            # Verify error was logged
            mock_logger.assert_called()
    
    @pytest.mark.asyncio
    async def test_webhook_retry_logic(self, webhook_handlers):
        """Test webhook retry logic for failed operations."""
        payload = '{"test": "webhook"}'
        
        # Mock a webhook that fails twice then succeeds
        call_count = 0
        async def mock_process_webhook(data):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return True
        
        with patch.object(webhook_handlers, 'process_webhook_event', side_effect=mock_process_webhook):
            result = await webhook_handlers.handle_webhook_with_retry(payload, max_retries=3)
            
            assert result is True
            assert call_count == 3  # Should have retried twice
    
    @pytest.mark.asyncio
    async def test_webhook_max_retries_exceeded(self, webhook_handlers):
        """Test webhook handling when max retries are exceeded."""
        payload = '{"test": "webhook"}'
        
        # Mock a webhook that always fails
        async def mock_process_webhook(data):
            raise Exception("Persistent failure")
        
        with patch.object(webhook_handlers, 'process_webhook_event', side_effect=mock_process_webhook), \
             patch('logging.Logger.error') as mock_logger:
            
            result = await webhook_handlers.handle_webhook_with_retry(payload, max_retries=3)
            
            assert result is False
            # Should have logged the final failure
            mock_logger.assert_called()
    
    @pytest.mark.asyncio
    async def test_missing_telegram_id_handling(self, stripe_service):
        """Test handling of webhooks with missing telegram_id in metadata."""
        webhook_data = {
            "id": "cs_test_session",
            "customer": "cus_test_customer",
            "metadata": {},  # No telegram_id
            "subscription": "sub_test_subscription"
        }
        
        with patch('logging.Logger.warning') as mock_logger:
            await stripe_service.handle_checkout_completed(webhook_data)
            
            # Should log warning about missing telegram_id
            mock_logger.assert_called()
    
    def test_get_payment_link(self, stripe_service):
        """Test payment link retrieval."""
        test_link = "https://buy.stripe.com/test_link"
        
        with patch('config.settings.StripeConfig.PAYMENT_LINK', test_link):
            result = stripe_service.get_payment_link()
            assert result == test_link
    
    def test_get_payment_link_missing(self, stripe_service):
        """Test payment link retrieval when not configured."""
        with patch('config.settings.StripeConfig.PAYMENT_LINK', None):
            result = stripe_service.get_payment_link()
            assert result is None
    
    @pytest.mark.asyncio
    async def test_notification_sending_failure_handling(self, stripe_service):
        """Test that notification sending failures don't break webhook processing."""
        telegram_id = 123456789
        
        with patch.object(stripe_service, 'bot') as mock_bot:
            mock_bot.send_message = AsyncMock(side_effect=Exception("Bot API error"))
            
            # Should not raise exception even if notification fails
            await stripe_service.send_premium_welcome_message(telegram_id)
            
            # Verify bot.send_message was called despite the error
            mock_bot.send_message.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__]) 