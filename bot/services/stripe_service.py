"""
Stripe integration service for handling subscription webhooks and premium management.
"""
import logging
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from typing import Optional, Dict

import pytz
import stripe
from config.settings import StripeConfig
from utils.user_management import update_premium_status
from utils.analytics_storage import SessionLocal, UserEvent

logger = logging.getLogger(__name__)

# Configure Stripe
if StripeConfig.API_KEY:
    stripe.api_key = StripeConfig.API_KEY

class StripeService:
    def __init__(self):
        self.webhook_secret = StripeConfig.WEBHOOK_SECRET
        self.payment_link = StripeConfig.PAYMENT_LINK
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify Stripe webhook signature to ensure authenticity.
        
        Args:
            payload: Raw webhook payload
            signature: Stripe signature header
            
        Returns:
            True if signature is valid
        """
        if not self.webhook_secret:
            logger.error("Stripe webhook secret not configured")
            return False
        
        try:
            # Extract timestamp and signature from header
            elements = signature.split(',')
            timestamp = None
            signature_hash = None
            
            for element in elements:
                key, value = element.split('=')
                if key == 't':
                    timestamp = value
                elif key == 'v1':
                    signature_hash = value
            
            if not timestamp or not signature_hash:
                logger.error("Invalid signature format")
                return False
            
            # Verify signature
            signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
            expected_signature = hmac.new(
                self.webhook_secret.encode('utf-8'),
                signed_payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(expected_signature, signature_hash):
                logger.error("Signature verification failed")
                return False
            
            # Check timestamp (prevent replay attacks)
            current_time = datetime.now(pytz.timezone('Asia/Singapore')).timestamp()
            webhook_time = int(timestamp)
            
            if abs(current_time - webhook_time) > 300:  # 5 minutes tolerance
                logger.error("Webhook timestamp too old")
                logger.error(f"Current time: {current_time}, Webhook time: {webhook_time}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False
    
    async def handle_checkout_completed(self, event_data: Dict) -> bool:
        """
        Handle successful checkout completion.
        
        Args:
            event_data: Stripe checkout.session.completed event data
            
        Returns:
            True if handled successfully
        """
        try:
            session = event_data['data']['object']
            customer_id = session.get('customer')

            if not customer_id:
                logger.error("No customer ID in checkout session")
                return False
            
            # Get subscription details
            subscription_id = session.get('subscription')
            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)

                # Access 'items' using square bracket notation
                # This ensures you get the actual data attribute, not the built-in method
                subscription_items_list_object = subscription['items']
                current_period_end_timestamp = subscription_items_list_object.data[0].current_period_end
                expires_at = datetime.fromtimestamp(current_period_end_timestamp)

                # Extract telegram_id from client_reference_id
                telegram_id = self._extract_telegram_id(session, customer_id)

                if telegram_id:
                    # Activate premium
                    success = await self.activate_premium(telegram_id, expires_at, customer_id)
                    if success:
                        self._log_event(telegram_id, "premium_activated", {
                            "customer_id": customer_id,
                            "subscription_id": subscription_id,
                            "expires_at": expires_at.isoformat()
                        })
                        return True
                else:
                    logger.error(f"Could not extract telegram_id from session {session['id']}")
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling checkout completed: {e}")
            return False
    
    async def handle_subscription_updated(self, event_data: Dict) -> bool:
        """
        Handle subscription lifecycle events (renewals, cancellations, etc.).
        
        Args:
            event_data: Stripe customer.subscription.updated event data
            
        Returns:
            True if handled successfully
        """
        try:
            subscription = event_data['data']['object']
            customer_id = subscription['customer']
            subscription_status = subscription['status']
            
            # Get telegram_id from customer
            telegram_id = await self._get_telegram_id_from_customer(customer_id)
            
            if not telegram_id:
                logger.error(f"Could not find telegram_id for customer {customer_id}")
                return False
            
            if subscription_status == 'active':
                # Subscription renewed or reactivated
                current_period_end_timestamp = subscription.items.data[0].current_period_end
                expires_at = datetime.fromtimestamp(current_period_end_timestamp)
                success = await self.activate_premium(telegram_id, expires_at, customer_id)
                
                if success:
                    self._log_event(telegram_id, "premium_renewed", {
                        "customer_id": customer_id,
                        "subscription_id": subscription['id'],
                        "expires_at": expires_at.isoformat()
                    })
                    return True
                    
            elif subscription_status in ['canceled', 'unpaid', 'incomplete_expired']:
                # Subscription cancelled or failed
                success = await self.deactivate_premium(telegram_id)
                
                if success:
                    self._log_event(telegram_id, "premium_deactivated", {
                        "customer_id": customer_id,
                        "subscription_id": subscription['id'],
                        "reason": subscription_status
                    })
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling subscription updated: {e}")
            return False
    
    async def activate_premium(self, telegram_id: int, expires_at: datetime, customer_id: str) -> bool:
        """
        Activate premium status for user.
        
        Args:
            telegram_id: Telegram user ID
            expires_at: When premium expires
            customer_id: Stripe customer ID
            
        Returns:
            True if activation successful
        """
        try:
            success = update_premium_status(
                telegram_id=telegram_id,
                premium=True,
                expires_at=expires_at,
                stripe_customer_id=customer_id
            )
            
            if success:
                # Clear quota counters for new premium user
                from services.usage_service import UsageService
                usage_service = UsageService()
                await usage_service.clear_premium_user_quotas(telegram_id)
                
                logger.info(f"Activated premium for user {telegram_id}, expires {expires_at}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error activating premium for {telegram_id}: {e}")
            return False
    
    async def deactivate_premium(self, telegram_id: int) -> bool:
        """
        Deactivate premium status for user.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            True if deactivation successful
        """
        try:
            success = update_premium_status(
                telegram_id=telegram_id,
                premium=False,
                expires_at=None
            )
            
            if success:
                logger.info(f"Deactivated premium for user {telegram_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deactivating premium for {telegram_id}: {e}")
            return False
    
    def _extract_telegram_id(self, session: Dict, customer_id: str) -> Optional[int]:
        """
        Extract telegram_id from session client_reference_id.
        
        Args:
            session: Stripe checkout session
            customer_id: Stripe customer ID
            
        Returns:
            Telegram user ID if found
        """
        try:
            logger.debug(f"Extracting telegram_id from session {session.get('id', 'unknown')}")
            
            # Try client_reference_id first (this is the main method now)
            if session.get('client_reference_id'):
                telegram_id = int(session['client_reference_id'])
                logger.info(f"Found telegram_id {telegram_id} in client_reference_id")
                
                # Update customer metadata with telegram_id for future reference
                stripe.Customer.modify(
                    customer_id,
                    metadata={
                        'telegram_id': str(telegram_id),
                        'linked_via': 'client_reference_id'
                    }
                )
                
                return telegram_id
            
            # Try session metadata as fallback
            if session.get('metadata') and session['metadata'].get('telegram_id'):
                telegram_id = int(session['metadata']['telegram_id'])
                logger.info(f"Found telegram_id {telegram_id} in session metadata")
                return telegram_id
            
            # Try customer metadata as fallback
            if customer_id:
                customer = stripe.Customer.retrieve(customer_id)
                logger.debug(f"Customer metadata: {customer.metadata}")
                if customer.metadata and customer.metadata.get('telegram_id'):
                    telegram_id = int(customer.metadata['telegram_id'])
                    logger.info(f"Found telegram_id {telegram_id} in customer metadata")
                    return telegram_id
            
            logger.warning(f"No telegram_id found in session {session.get('id')}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting telegram_id: {e}")
            return None
    
    async def _get_telegram_id_from_customer(self, customer_id: str) -> Optional[int]:
        """
        Get telegram_id from Stripe customer or database.
        
        Args:
            customer_id: Stripe customer ID
            
        Returns:
            Telegram user ID if found
        """
        try:
            # Try customer metadata first
            customer = stripe.Customer.retrieve(customer_id)
            if customer.metadata and customer.metadata.get('telegram_id'):
                return int(customer.metadata['telegram_id'])
            
            # Try database lookup
            from utils.analytics_storage import SessionLocal, User
            with SessionLocal() as session:
                user = session.query(User).filter_by(stripe_customer_id=customer_id).first()
                if user:
                    return user.telegram_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting telegram_id for customer {customer_id}: {e}")
            return None
    
    def _log_event(self, telegram_id: int, event_type: str, extra_data: Dict):
        """
        Log premium-related events for analytics.
        
        Args:
            telegram_id: Telegram user ID
            event_type: Type of event
            extra_data: Additional event data
        """
        try:
            with SessionLocal() as session:
                event = UserEvent(
                    user_id=telegram_id,
                    chat_id=0,  # Not chat-specific
                    event_type=event_type,
                    extra=json.dumps(extra_data)
                )
                session.add(event)
                session.commit()
                
        except Exception as e:
            logger.error(f"Error logging event {event_type} for {telegram_id}: {e}")
    
    def get_payment_link(self) -> Optional[str]:
        """Get the Stripe payment link for subscriptions."""
        return self.payment_link
