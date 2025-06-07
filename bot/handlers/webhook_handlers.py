"""
Webhook handlers for Stripe integration.
Handles incoming Stripe webhooks for subscription management.
"""
import json
import logging
from typing import Dict, Any
import stripe
from telegram.ext import Application

from services.stripe_service import StripeService
from utils.analytics_storage import log_user_event

logger = logging.getLogger(__name__)

class WebhookHandlers:
    def __init__(self, application: Application):
        self.stripe_service = StripeService()
        self.application = application
    
    async def handle_stripe_webhook(self, request) -> Dict[str, Any]:
        """
        Handle incoming Stripe webhook requests.
        
        Args:
            request: HTTP request object with webhook data
            
        Returns:
            Dict with status and message for HTTP response
        """
        try:
            # Get request body and signature
            if hasattr(request, 'body'):
                body = request.body
            elif hasattr(request, 'data'):
                body = request.data
            else:
                logger.error("Could not extract body from webhook request")
                return {"status": 400, "message": "Invalid request body"}
            
            # Get Stripe signature header
            signature = None
            if hasattr(request, 'headers'):
                signature = request.headers.get('Stripe-Signature')
            elif hasattr(request, 'META'):
                signature = request.META.get('HTTP_STRIPE_SIGNATURE')
            
            if not signature:
                logger.error("No Stripe signature found in webhook request")
                return {"status": 400, "message": "Missing Stripe signature"}
            
            # Verify webhook signature
            if not self.stripe_service.verify_webhook_signature(body, signature):
                logger.error("Stripe webhook signature verification failed")
                return {"status": 401, "message": "Invalid signature"}
            
            # Parse webhook data
            try:
                event_data = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse webhook JSON: {e}")
                return {"status": 400, "message": "Invalid JSON"}
            
            # Handle different event types
            event_type = event_data.get('type')
            success = False
            
            if event_type == 'checkout.session.completed':
                success = await self.stripe_service.handle_checkout_completed(event_data)
                if success:
                    # Send welcome message to user
                    await self._send_premium_welcome(event_data)
                    
            elif event_type == 'customer.subscription.updated':
                success = await self.stripe_service.handle_subscription_updated(event_data)
                if success:
                    # Send appropriate notification to user
                    await self._send_subscription_notification(event_data)
                    
            elif event_type == 'customer.subscription.deleted':
                # Handle actual subscription deletion (when subscription ends)
                success = await self.stripe_service.handle_subscription_deleted(event_data)
                if success:
                    await self._send_downgrade_notification(event_data)
                    
            elif event_type == 'invoice.payment_failed':
                # Handle payment failures
                success = await self.stripe_service.handle_subscription_updated(event_data)
                if success:
                    await self._send_downgrade_notification(event_data)
                    
            else:
                logger.info(f"Unhandled Stripe webhook event type: {event_type}")
                success = True  # Don't fail for unhandled events
            
            if success:
                logger.info(f"Successfully processed Stripe webhook: {event_type}")
                return {"status": 200, "message": "Webhook processed successfully"}
            else:
                logger.error(f"Failed to process Stripe webhook: {event_type}")
                return {"status": 500, "message": "Webhook processing failed"}
                
        except Exception as e:
            logger.error(f"Error processing Stripe webhook: {e}")
            return {"status": 500, "message": "Internal server error"}
    
    async def _send_premium_welcome(self, event_data: Dict):
        """Send welcome message to new premium user."""
        try:
            session = event_data['data']['object']
            customer_id = session.get('customer')
            
            # Extract telegram_id from session or customer
            telegram_id = self.stripe_service._extract_telegram_id(session, customer_id)
            
            if telegram_id:
                welcome_message = (
                    "🎉 *Welcome to Premium!*\n\n"
                    "You now have unlimited access to:\n"
                    "• ∞ Daily summaries\n"
                    "• ∞ Monthly summaries\n" 
                    "• ∞ Group chats\n\n"
                    "Thank you for supporting the bot! 🚀"
                )
                
                await self.application.bot.send_message(
                    chat_id=telegram_id,
                    text=welcome_message,
                    parse_mode="Markdown"
                )
                
                # Log the event
                log_user_event(
                    user_id=telegram_id,
                    chat_id=telegram_id,
                    event_type="premium_welcome_sent",
                    extra="Sent premium welcome message"
                )
                
        except Exception as e:
            logger.error(f"Error sending premium welcome message: {e}")
    
    async def _send_subscription_notification(self, event_data: Dict):
        """Send notification for subscription updates (renewals, etc.)."""
        try:
            session = event_data['data']['object']
            customer_id = session.get('customer')
            subscription_status = session.get('status')
            cancel_at_period_end = session.get('cancel_at_period_end', False)
            subscription_id = session['id']
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            # Get telegram_id from customer
            telegram_id = await self.stripe_service._get_telegram_id_from_customer(customer_id)
            
            if telegram_id:
                if subscription_status == 'active' and cancel_at_period_end:
                    # Subscription is scheduled for cancellation
                    from datetime import datetime
                    subscription_items_list_object = subscription['items']  
                    current_period_end_timestamp = subscription_items_list_object.data[0].current_period_end
                    period_end = datetime.fromtimestamp(current_period_end_timestamp)
                    period_end_str = period_end.strftime("%B %d, %Y")
                    
                    cancellation_message = (
                        "📅 *Subscription Cancellation Confirmed*\n\n"
                        f"Your premium subscription has been scheduled for cancellation.\n"
                        f"You'll continue to have full premium access until {period_end_str}.\n\n"
                        "If you change your mind, you can reactivate your subscription anytime before it ends."
                    )

                    await self.application.bot.send_message(
                        chat_id=telegram_id,
                        text=cancellation_message,
                        parse_mode="Markdown"
                    )
                    
                elif subscription_status == 'active' and not cancel_at_period_end:
                    # Subscription renewed or reactivated
                    renewal_message = (
                        "✅ *Premium Renewed*\n\n"
                        "Your premium subscription has been renewed successfully.\n"
                        "You continue to have unlimited access to all features! 🚀"
                    )
                    
                    await self.application.bot.send_message(
                        chat_id=telegram_id,
                        text=renewal_message,
                        parse_mode="Markdown"
                    )
                
        except Exception as e:
            logger.error(f"Error sending subscription notification: {e}")
    
    async def _send_downgrade_notification(self, event_data: Dict):
        """Send notification when user is downgraded from premium."""
        try:
            if event_data['type'] == 'customer.subscription.updated':
                subscription = event_data['data']['object']
                customer_id = subscription['customer']
            else:  # subscription.deleted or payment_failed
                obj = event_data['data']['object']
                customer_id = obj.get('customer')
            
            # Get telegram_id from customer
            telegram_id = await self.stripe_service._get_telegram_id_from_customer(customer_id)
            
            if telegram_id:
                downgrade_message = (
                    "📉 *Premium Subscription Ended*\n\n"
                    "Your premium subscription has ended. You're now on the free plan:\n\n"
                    "• 5 summaries per day\n"
                    "• 100 summaries per month\n"
                    "• 3 group chats maximum\n\n"
                    "To continue unlimited access, use /upgrade to resubscribe."
                )
                
                await self.application.bot.send_message(
                    chat_id=telegram_id,
                    text=downgrade_message,
                    parse_mode="Markdown"
                )
                
        except Exception as e:
            logger.error(f"Error sending downgrade notification: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check endpoint for webhook server."""
        try:
            # Test Stripe service connectivity
            has_payment_link = self.stripe_service.get_payment_link() is not None
            
            # Test database connectivity
            from utils.user_management import get_or_create_user
            test_user = get_or_create_user(999999999)  # Test with dummy ID
            db_ok = test_user is not None
            
            if has_payment_link and db_ok:
                return {"status": 200, "message": "Webhook service healthy"}
            else:
                return {"status": 503, "message": "Webhook service unhealthy"}
                
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"status": 503, "message": "Health check failed"} 