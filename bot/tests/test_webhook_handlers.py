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
from datetime import datetime


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
        payload = b'{"test": "data"}'  # Use bytes instead of string
        secret = "whsec_test_secret"
        
        # Create valid signature
        import time
        timestamp = str(int(time.time()))
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        signature = hmac.new(
            secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        sig_header = f"t={timestamp},v1={signature}"
        
        # Patch the instance attribute directly since it's set in __init__
        stripe_service.webhook_secret = secret
        result = stripe_service.verify_webhook_signature(payload, sig_header)
        assert result is True
    
    def test_webhook_signature_verification_invalid(self, stripe_service):
        """Test that invalid webhook signatures are rejected."""
        payload = b'{"test": "data"}'  # Use bytes instead of string
        secret = "whsec_test_secret"
        invalid_signature = "invalid_signature"
        sig_header = f"t=1234567890,v1={invalid_signature}"
        
        # Patch the instance attribute directly since it's set in __init__
        stripe_service.webhook_secret = secret
        result = stripe_service.verify_webhook_signature(payload, sig_header)
        assert result is False
    
    def test_webhook_signature_verification_missing_secret(self, stripe_service):
        """Test webhook verification when secret is missing."""
        payload = b'{"test": "data"}'  # Use bytes instead of string
        sig_header = "t=1234567890,v1=signature"
        
        # Set webhook secret to None to test missing secret scenario
        stripe_service.webhook_secret = None
        result = stripe_service.verify_webhook_signature(payload, sig_header)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_checkout_session_completed_handler(self, stripe_service, sample_webhook_payload):
        """Test successful checkout session completion handling."""
        telegram_id = 123456789
        customer_id = "cus_test_customer"
        
        # Mock the subscription retrieval and other dependencies
        mock_subscription = Mock()
        mock_subscription.__getitem__ = Mock(side_effect=lambda key: {
            'items': Mock(data=[Mock(current_period_end=1234567890)])
        }[key])
        
        with patch('services.stripe_service.update_premium_status', return_value=True) as mock_update_premium, \
             patch('stripe.Subscription.retrieve', return_value=mock_subscription), \
             patch.object(stripe_service, '_extract_telegram_id', return_value=telegram_id), \
             patch.object(stripe_service, '_log_event') as mock_log_event, \
             patch('services.usage_service.UsageService') as mock_usage_service_class:
            
            mock_usage_service = Mock()
            mock_usage_service.clear_premium_user_quotas = AsyncMock()
            mock_usage_service_class.return_value = mock_usage_service
            
            result = await stripe_service.handle_checkout_completed(sample_webhook_payload)
            
            # Verify the result is True (successful processing)
            assert result is True
            
            # Verify premium status was updated
            mock_update_premium.assert_called_once()
            args = mock_update_premium.call_args[1]  # Use keyword args
            assert args['telegram_id'] == telegram_id
            assert args['premium'] is True
            assert args['stripe_customer_id'] == customer_id
    
    @pytest.mark.asyncio
    async def test_subscription_updated_renewal(self, stripe_service):
        """Test subscription renewal handling."""
        subscription_data = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test",
                    "customer": "cus_test_customer",
                    "status": "active",
                    "items": Mock(data=[Mock(current_period_end=1234567890)]),
                    "metadata": {
                        "telegram_id": "123456789"
                    }
                }
            }
        }
        
        # Mock the subscription retrieval
        mock_subscription = Mock()
        mock_subscription.__getitem__ = Mock(side_effect=lambda key: {
            'items': Mock(data=[Mock(current_period_end=1234567890)])
        }[key])
        
        with patch('services.stripe_service.update_premium_status', return_value=True) as mock_update_premium, \
             patch('stripe.Subscription.retrieve', return_value=mock_subscription), \
             patch.object(stripe_service, '_get_telegram_id_from_customer', return_value=123456789), \
             patch.object(stripe_service, '_log_event'), \
             patch('services.usage_service.UsageService') as mock_usage_service_class:
            
            mock_usage_service = Mock()
            mock_usage_service.clear_premium_user_quotas = AsyncMock()
            mock_usage_service_class.return_value = mock_usage_service
            
            result = await stripe_service.handle_subscription_updated(subscription_data)
            
            # Verify the result is True (successful processing)
            assert result is True
            
            # Verify premium status was updated with new expiry
            mock_update_premium.assert_called_once()
            args = mock_update_premium.call_args[1]  # Use keyword args
            assert args['telegram_id'] == 123456789
            assert args['premium'] is True
    
    @pytest.mark.asyncio
    async def test_subscription_updated_cancellation(self, stripe_service):
        """Test subscription cancellation handling."""
        subscription_data = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test",
                    "customer": "cus_test_customer",
                    "status": "canceled",
                    "metadata": {
                        "telegram_id": "123456789"
                    }
                }
            }
        }
        
        with patch('services.stripe_service.update_premium_status', return_value=True) as mock_update_premium, \
             patch('stripe.Subscription.retrieve', return_value=Mock()), \
             patch.object(stripe_service, '_get_telegram_id_from_customer', return_value=123456789), \
             patch.object(stripe_service, '_log_event'):
            
            result = await stripe_service.handle_subscription_updated(subscription_data)
            
            # Verify the result is True (successful processing)
            assert result is True
            
            # Verify premium status was deactivated
            mock_update_premium.assert_called_once()
            args = mock_update_premium.call_args[1]  # Use keyword args
            assert args['telegram_id'] == 123456789
            assert args['premium'] is False
    
    @pytest.mark.asyncio
    async def test_subscription_deleted_handler(self, stripe_service):
        """Test subscription deletion handling."""
        subscription_data = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_test",
                    "customer": "cus_test_customer"
                }
            }
        }
        
        with patch('services.stripe_service.update_premium_status', return_value=True) as mock_update_premium, \
             patch.object(stripe_service, '_get_telegram_id_from_customer', return_value=123456789), \
             patch.object(stripe_service, '_log_event'):
            
            result = await stripe_service.handle_subscription_deleted(subscription_data)
            
            # Verify the result is True (successful processing)
            assert result is True
            
            # Verify premium status was deactivated
            mock_update_premium.assert_called_once()
            args = mock_update_premium.call_args[1]  # Use keyword args
            assert args['telegram_id'] == 123456789
            assert args['premium'] is False
            assert args['expires_at'] is None
    
    @pytest.mark.asyncio
    async def test_subscription_scheduled_for_cancellation(self, stripe_service):
        """Test subscription scheduled for cancellation (cancel_at_period_end=True)."""
        subscription_data = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test",
                    "customer": "cus_test_customer",
                    "status": "active",
                    "cancel_at_period_end": True,
                    "current_period_end": 1234567890
                }
            }
        }
        
        mock_subscription = Mock()
        mock_subscription.current_period_end = 1234567890
        mock_subscription.__getitem__ = Mock(side_effect=lambda key: {
            'items': Mock(data=[Mock(current_period_end=1234567890)])
        }[key])
        
        with patch('stripe.Subscription.retrieve', return_value=mock_subscription), \
             patch.object(stripe_service, '_get_telegram_id_from_customer', return_value=123456789), \
             patch.object(stripe_service, '_log_event'), \
             patch('services.stripe_service.update_premium_status') as mock_update_premium:
            
            result = await stripe_service.handle_subscription_updated(subscription_data)
            
            # Verify the result is True (successful processing)
            assert result is True
            
            # Verify premium status was NOT changed (user keeps access until period end)
            mock_update_premium.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_premium_activation_redis_cleanup(self, stripe_service):
        """Test that premium activation clears Redis quota counters."""
        telegram_id = 123456789
        expires_at = datetime(2024, 12, 31, 23, 59, 59)
        customer_id = "cus_test_customer"
        
        with patch('utils.user_management.update_premium_status', return_value=True) as mock_update_premium, \
             patch('services.usage_service.UsageService') as mock_usage_service_class:
            
            mock_usage_service = Mock()
            mock_usage_service.clear_premium_user_quotas = AsyncMock()
            mock_usage_service_class.return_value = mock_usage_service
            
            result = await stripe_service.activate_premium(telegram_id, expires_at, customer_id)
            
            # Verify activation was successful
            assert result is True
            
            # Verify quota counters were cleared
            mock_usage_service.clear_premium_user_quotas.assert_called_once_with(telegram_id)
    
    @pytest.mark.asyncio
    async def test_premium_deactivation_redis_cleanup(self, stripe_service):
        """Test that premium deactivation updates user status."""
        telegram_id = 123456789
        
        with patch('services.stripe_service.update_premium_status', return_value=True) as mock_update_premium:
            
            result = await stripe_service.deactivate_premium(telegram_id)
            
            # Verify deactivation was successful
            assert result is True
            
            # Verify premium status was updated to False
            mock_update_premium.assert_called_once()
            args = mock_update_premium.call_args[1]  # Use keyword args
            assert args['telegram_id'] == telegram_id
            assert args['premium'] is False
            assert args['expires_at'] is None
    
    @pytest.mark.asyncio
    async def test_webhook_error_handling_database_failure(self, stripe_service, sample_webhook_payload):
        """Test webhook error handling when database operations fail."""
        with patch('services.stripe_service.update_premium_status', return_value=False), \
             patch.object(stripe_service, '_extract_telegram_id', return_value=123456789), \
             patch('stripe.Subscription.retrieve') as mock_retrieve, \
             patch('logging.Logger.error') as mock_logger:
            
            mock_subscription = Mock()
            mock_subscription.__getitem__ = Mock(side_effect=lambda key: {
                'items': Mock(data=[Mock(current_period_end=1234567890)])
            }[key])
            mock_retrieve.return_value = mock_subscription
            
            # Should return False when database operation fails
            result = await stripe_service.handle_checkout_completed(sample_webhook_payload)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_webhook_retry_logic(self, webhook_handlers):
        """Test webhook retry logic for failed operations."""
        # Create a mock request object
        mock_request = Mock()
        mock_request.body = b'{"type": "checkout.session.completed", "data": {"object": {}}}'
        mock_request.headers = {'Stripe-Signature': 'test_signature'}
        
        # Mock successful signature verification but failed processing
        with patch.object(webhook_handlers.stripe_service, 'verify_webhook_signature', return_value=True), \
             patch.object(webhook_handlers.stripe_service, 'handle_checkout_completed', return_value=False):
            
            result = await webhook_handlers.handle_stripe_webhook(mock_request)
            
            # Should return error status when processing fails
            assert result['status'] == 500
            assert 'failed' in result['message'].lower()
    
    @pytest.mark.asyncio
    async def test_webhook_max_retries_exceeded(self, webhook_handlers):
        """Test webhook handling when signature verification fails."""
        # Create a mock request object
        mock_request = Mock()
        mock_request.body = b'{"type": "test.event", "data": {"object": {}}}'
        mock_request.headers = {'Stripe-Signature': 'invalid_signature'}
        
        # Mock failed signature verification
        with patch.object(webhook_handlers.stripe_service, 'verify_webhook_signature', return_value=False):
            
            result = await webhook_handlers.handle_stripe_webhook(mock_request)
            
            # Should return 401 for invalid signature
            assert result['status'] == 401
            assert 'signature' in result['message'].lower()
    
    @pytest.mark.asyncio
    async def test_missing_telegram_id_handling(self, stripe_service):
        """Test handling of webhooks with missing telegram_id in metadata."""
        webhook_data = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_session",
                    "customer": "cus_test_customer",
                    "metadata": {},  # No telegram_id
                    "subscription": "sub_test_subscription"
                }
            }
        }
        
        with patch.object(stripe_service, '_extract_telegram_id', return_value=None), \
             patch('stripe.Subscription.retrieve') as mock_retrieve:
            
            mock_subscription = Mock()
            mock_subscription.__getitem__ = Mock(side_effect=lambda key: {
                'items': Mock(data=[Mock(current_period_end=1234567890)])
            }[key])
            mock_retrieve.return_value = mock_subscription
            
            result = await stripe_service.handle_checkout_completed(webhook_data)
            
            # Should return False when telegram_id is missing
            assert result is False
    
    def test_get_payment_link(self, stripe_service):
        """Test payment link retrieval."""
        test_link = "https://buy.stripe.com/test_link"
        
        # Mock the payment_link attribute directly
        stripe_service.payment_link = test_link
        result = stripe_service.get_payment_link()
        assert result == test_link
    
    def test_get_payment_link_missing(self, stripe_service):
        """Test payment link retrieval when not configured."""
        # Mock the payment_link attribute as None
        stripe_service.payment_link = None
        result = stripe_service.get_payment_link()
        assert result is None
    
    @pytest.mark.asyncio
    async def test_webhook_successful_processing(self, webhook_handlers):
        """Test successful webhook processing."""
        # Create a mock request object
        mock_request = Mock()
        mock_request.body = b'{"type": "checkout.session.completed", "data": {"object": {}}}'
        mock_request.headers = {'Stripe-Signature': 'test_signature'}
        
        # Mock successful signature verification and processing
        with patch.object(webhook_handlers.stripe_service, 'verify_webhook_signature', return_value=True), \
             patch.object(webhook_handlers.stripe_service, 'handle_checkout_completed', return_value=True), \
             patch.object(webhook_handlers, '_send_premium_welcome') as mock_welcome:
            
            result = await webhook_handlers.handle_stripe_webhook(mock_request)
            
            # Should return success status
            assert result['status'] == 200
            assert 'success' in result['message'].lower()


if __name__ == "__main__":
    pytest.main([__file__]) 