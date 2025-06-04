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
            session = event_data['data']['object']
            customer_id = session.get('customer')
            subscription_status = session['status']
            subscription_id = session['id']
            cancel_at_period_end = session.get('cancel_at_period_end', False)
            subscription = stripe.Subscription.retrieve(subscription_id)

            # Get telegram_id from customer
            telegram_id = await self._get_telegram_id_from_customer(customer_id)
            
            if not telegram_id:
                logger.error(f"Could not find telegram_id for customer {customer_id}")
                return False

            logger.info(f"Subscription status: {subscription_status}")
            logger.info(f"Cancel at period end: {cancel_at_period_end}")
            
            if subscription_status == 'active':
                # Check if subscription is scheduled for cancellation
                if cancel_at_period_end:
                    # Subscription is scheduled to cancel at period end
                    logger.info(f"Subscription {subscription_id} is scheduled for cancellation at period end")

                    subscription_items_list_object = subscription['items']  
                    current_period_end_timestamp = subscription_items_list_object.data[0].current_period_end
                    period_end = datetime.fromtimestamp(current_period_end_timestamp)
                    
                    self._log_event(telegram_id, "premium_scheduled_for_cancellation", {
                        "customer_id": customer_id,
                        "subscription_id": subscription_id,
                        "cancel_at_period_end": True,
                        "period_end": period_end.isoformat()
                    })

                    logger.info(f"Period end: {period_end}")
                    
                    # Don't change premium status yet - user keeps access until period end
                    return True
                else:
                    # Subscription renewed or reactivated (or cancellation was stopped)
                    logger.info(f"Subscription renewed, reactivated, or cancellation stopped")
                    subscription_items_list_object = subscription['items']
                    current_period_end_timestamp = subscription_items_list_object.data[0].current_period_end
                    expires_at = datetime.fromtimestamp(current_period_end_timestamp)
                    success = await self.activate_premium(telegram_id, expires_at, customer_id)
                    
                    if success:
                        self._log_event(telegram_id, "premium_renewed", {
                            "customer_id": customer_id,
                            "subscription_id": subscription_id,
                            "expires_at": expires_at.isoformat()
                        })
                        return True
                    
            elif subscription_status in ['canceled', 'unpaid', 'incomplete_expired']:
                # Subscription cancelled or failed
                logger.info(f"Subscription cancelled or failed with status: {subscription_status}")
                success = await self.deactivate_premium(telegram_id)
                
                if success:
                    self._log_event(telegram_id, "premium_deactivated", {
                        "customer_id": customer_id,
                        "subscription_id": subscription_id,
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
    
    async def cancel_subscription_by_telegram_id(self, telegram_id: int) -> Dict[str, any]:
        """
        Cancel subscription for a user by their Telegram ID.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            Dict with success status and message
        """
        try:
            # Get stripe_customer_id from database
            from utils.analytics_storage import SessionLocal, User
            stripe_customer_id = None
            
            with SessionLocal() as session:
                user = session.query(User).filter_by(telegram_id=telegram_id).first()
                if user and user.stripe_customer_id:
                    stripe_customer_id = user.stripe_customer_id
            
            if not stripe_customer_id:
                return {
                    "success": False, 
                    "message": "You don't have an active premium subscription to cancel."
                }
            
            # Find active subscription
            subscriptions = stripe.Subscription.list(
                customer=stripe_customer_id,
                status='active',
                limit=1
            )
            
            if not subscriptions.data:
                return {
                    "success": False,
                    "message": "You don't have an active subscription to cancel."
                }
            
            subscription = subscriptions.data[0]
            subscription_id = subscription.id
            
            # Cancel at period end (user-friendly approach)
            try:
                updated_subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )

                subscription_items_list_object = updated_subscription['items']  
                current_period_end_timestamp = subscription_items_list_object.data[0].current_period_end
                period_end = datetime.fromtimestamp(current_period_end_timestamp)
                
                # Get period end date for user message
                period_end_str = period_end.strftime("%B %d, %Y")

                logger.info(f"Period end: {period_end}")
                
                # Log the cancellation event
                self._log_event(telegram_id, "premium_cancelled_by_user", {
                    "customer_id": stripe_customer_id,
                    "subscription_id": subscription_id,
                    "cancel_at_period_end": True,
                    "period_end": period_end.isoformat()
                })
                
                logger.info(f"User {telegram_id} cancelled subscription {subscription_id}, ends {period_end}")
                
                return {
                    "success": True,
                    "message": f"Your premium subscription has been cancelled. You'll continue to have premium access until {period_end_str}."
                }
                
            except stripe.error.StripeError as e:
                logger.error(f"Stripe error cancelling subscription {subscription_id}: {e}")
                return {
                    "success": False,
                    "message": "There was an error cancelling your subscription. Please try again later."
                }
            
        except Exception as e:
            logger.error(f"Error cancelling subscription for user {telegram_id}: {e}")
            return {
                "success": False,
                "message": "There was an error processing your cancellation request. Please try again later."
            }
    
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

    async def handle_subscription_deleted(self, event_data: Dict) -> bool:
        """
        Handle subscription deletion event (when subscription actually ends).
        
        Args:
            event_data: Stripe customer.subscription.deleted event data
            
        Returns:
            True if handled successfully
        """
        try:
            subscription = event_data['data']['object']
            customer_id = subscription.get('customer')
            subscription_id = subscription['id']

            # Get telegram_id from customer
            telegram_id = await self._get_telegram_id_from_customer(customer_id)
            
            if not telegram_id:
                logger.error(f"Could not find telegram_id for customer {customer_id}")
                return False
            
            # Deactivate premium status
            logger.info(f"Subscription {subscription_id} deleted, deactivating premium")
            success = await self.deactivate_premium(telegram_id)
            
            if success:
                self._log_event(telegram_id, "premium_deactivated", {
                    "customer_id": customer_id,
                    "subscription_id": subscription_id,
                    "reason": "subscription_deleted"
                })
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling subscription deleted: {e}")
            return False
