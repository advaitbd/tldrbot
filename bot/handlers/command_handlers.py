# Add necessary imports
import time
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent, PhotoSize, InlineKeyboardButton, InlineKeyboardMarkup
from uuid import uuid4
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler as TelegramCommandHandler, # Rename to avoid clash
    MessageHandler, filters
)
from services.ai import StrategyRegistry
from utils.memory_storage import MemoryStorage
from services.ai.ai_service import AIService
from utils.text_processor import TextProcessor
from utils.analytics_storage import log_user_event  # <-- NEW
from utils.user.user_api_keys import set_user_api_key, get_user_api_key, clear_user_api_key, get_all_user_keys
import logging
from config.settings import OpenAIConfig, GroqAIConfig, DeepSeekConfig, StripeConfig
from services.ai.openai_strategy import OpenAIStrategy
from services.ai.groq_strategy import GroqAIStrategy
from services.ai.deepseek_strategy import DeepSeekStrategy

# Import freemium services
from services.usage_service import UsageService
from services.stripe_service import StripeService
from utils.user_management import is_premium

# Import the new bill splitting service functions
from services.bill_splitter import (
    extract_receipt_data_from_image,
    parse_payment_context_with_llm,
    calculate_split,
    format_split_results,
    ReceiptData # Import ReceiptData for type hinting if needed
)
from io import BytesIO
from services.redis_queue import RedisQueue

logger = logging.getLogger(__name__)

# Define conversation states
RECEIPT_IMAGE, CONFIRMATION = range(2)

class CommandHandlers:
    def __init__(self, memory_storage: MemoryStorage, redis_queue: RedisQueue | None = None):
        self.memory_storage = memory_storage
        self.redis_queue = redis_queue
        self.ai_service = AIService(StrategyRegistry.get_strategy("deepseek"))
        self.text_processor = TextProcessor()
        self.user_selected_model = {}
        
        # Initialize freemium services
        self.usage_service = UsageService()
        self.stripe_service = StripeService()
    #     self.user_subscription = {}  # {user_id: subscription_status}

    # async def subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    #     user = update.effective_user
    #     if user is None or update.message is None:
    #         return
    #     self.user_subscription[user.id] = True
    #     await update.message.reply_text("You are now subscribed to the bot. You will receive a notification when a new message is posted.")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # --- Analytics logging ---
        user = update.effective_user
        chat = update.effective_chat
        if user is not None and chat is not None:
            log_user_event(
                user_id=user.id,
                chat_id=chat.id,
                event_type="help_command",
                username=getattr(user, "username", None),
                first_name=getattr(user, "first_name", None),
                last_name=getattr(user, "last_name", None),
                llm_name=self.ai_service.get_current_model(),
            )
        # --- End analytics logging ---

        # Get usage statistics for the user
        usage_info = ""
        if user:
            try:
                usage_string = await self.usage_service.format_usage_string(user.id)
                # If user is not premium, suggest upgrade
                usage_info = f"\n\n*Account & Usage:*\n{usage_string}"
                if not is_premium(user.id):
                    usage_info += "\n\n*Upgrade to Premium for unlimited access* with /upgrade"


            except Exception as e:
                logger.error(f"Error getting usage info for help command: {e}")
                usage_info = "\n\n*Account & Usage:* Unable to load usage information"

        help_text = (
            "🤖 *Welcome to TLDR Bot!* 🤖\n\n"
            "I help you summarize conversations and provide insights. Here's what I can do:\n\n"
            "*Commands:*\n"
            "• `/tldr [number]` — Summarize the last [number] messages (default: 50)\n"
            "• `/dl [URL]` — Download TikToks, Reels, Shorts, etc. (WIP: might not work sometimes)\n"
            "• `/switch_model <provider>` — Change the AI model\n"
            "• `/set_api_key <provider> <key>` — Set your own API key for a provider (BYOK)\n"
            "    Valid providers: `openai`, `groq`, `deepseek`\n"
            "• `/clear_api_key <provider>` — Remove your API key for a provider\n"
            "• `/list_providers` — List all valid provider names\n"
            "• `/upgrade` — Upgrade to Premium for unlimited access\n"
            "• `/usage` — Check your current usage statistics\n"
            "\n*Available Models:*\n"
            "• `openai` — OpenAI GPT models\n"
            "• `groq` — Uses Llama 3 (8bn) hosted by groq\n"
            "• `deepseek` — DeepSeek V3\n"
            "\n*Features:*\n"
            "• Reply to my summaries with questions for more insights\n"
            "• View sentiment analysis in summaries\n"
            "• Get key events extracted from conversations\n"
            f"{usage_info}\n"
            "\n*Current model:* " + str(self.ai_service.get_current_model())
        )

        if update.message:
            await update.message.reply_text(help_text, parse_mode="Markdown")
        else:
            logger.warning("No message found in update for help_command.")

    def _get_user_strategy(self, user_id: int, provider: str):
        """Return a strategy for the provider, using user key if available."""
        provider = provider.lower()
        return self._resolve_strategy(
            user_id,
            provider,
            {
                "openai": (OpenAIConfig, OpenAIStrategy),
                "groq": (GroqAIConfig, GroqAIStrategy),
                "deepseek": (DeepSeekConfig, DeepSeekStrategy),
            },
        )

    def _resolve_strategy(self, user_id: int, provider: str, config_map: dict):
        """Helper function to resolve API key and model for a given provider."""
        if provider not in config_map:
            raise ValueError(f"Unknown provider: {provider}")

        config_class, strategy_class = config_map[provider]
        user_key = get_user_api_key(user_id, provider)
        key = user_key if user_key is not None else (config_class.API_KEY if config_class.API_KEY is not None else "")
        model = config_class.MODEL if config_class.MODEL is not None else ""
        return strategy_class(key, model)
    def _get_user_selected_model(self, user_id: int):
        """Get the user's selected model/provider, or default to 'deepseek'."""
        return self.user_selected_model.get(user_id, "deepseek")

    async def summarize(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # --- Analytics logging ---
        user = update.effective_user
        chat = update.effective_chat
        if user is not None and chat is not None:
            log_user_event(
                user_id=user.id,
                chat_id=chat.id,
                event_type="summarize_command",
                username=getattr(user, "username", None),
                first_name=getattr(user, "first_name", None),
                last_name=getattr(user, "last_name", None),
                llm_name=self.ai_service.get_current_model(),
            )
        # --- End analytics logging ---

        if not update.effective_chat or not hasattr(update.effective_chat, "id"):
            logger.error("No effective_chat or chat id found in update.")
            if update.message:
                await update.message.reply_text("Could not determine chat context.")
            return

        chat_id = update.effective_chat.id
        
        # FREEMIUM: Check quota before processing
        if user:
            try:
                # Track performance for quota checks
                quota_start_time = time.time()
                
                # Check if user is within quota
                within_quota = await self.usage_service.within_quota(user.id, chat_id)
                
                # Log performance metrics
                quota_end_time = time.time()
                quota_duration = (quota_end_time - quota_start_time) * 1000  # Convert to ms
                
                if quota_duration > 50:  # Log if quota check took longer than 50ms
                    logger.warning(f"Quota check took {quota_duration:.2f}ms for user {user.id}")
                else:
                    logger.debug(f"Quota check completed in {quota_duration:.2f}ms for user {user.id}")
                
                if not within_quota:
                    # Block the command and send DM
                    await self._block_and_dm(user.id, update)
                    return
                    
            except Exception as e:
                logger.error(f"Error checking quota for user {user.id}: {e}")
                # Fail-safe: allow premium users, block others
                if not is_premium(user.id):
                    if update.message:
                        await update.message.reply_text("Service temporarily unavailable. Please try again later.")
                    return

        num_messages = self._parse_message_count(getattr(context, "args", None), default=50, max_limit=400)

        if not num_messages:
            if update.message:
                await update.message.reply_text("Invalid message count")
            return

        memory_storage = self.memory_storage
        messages_list = memory_storage.get_recent_messages(chat_id, num_messages)
        combined_text = "\n".join(messages_list)
        summary_prompt = self._create_summary_prompt(combined_text)

        # Immediately reply to user
        if update.message:
            await update.message.reply_text("Summarizing... I'll send the summary here when it's ready! 📝")
        else:
            await context.bot.send_message(chat_id=chat_id, text="Summarizing... I'll send the summary here when it's ready! 📝")

        # FREEMIUM: Increment usage counters for successful requests
        if user:
            try:
                counters = await self.usage_service.increment_counters(user.id, chat_id)
                logger.info(f"Updated usage counters for user {user.id}: {counters}")
            except Exception as e:
                logger.error(f"Error incrementing counters for user {user.id}: {e}")

        # Use user's selected model/provider and key if available
        provider = self._get_user_selected_model(user.id if user is not None else 0)
        try:
            strategy = self._get_user_strategy(user.id if user is not None else 0, provider)
            self.ai_service.set_strategy(strategy)
        except Exception as e:
            logger.error(f"Error setting user strategy: {str(e)}")
            # fallback to default
            self.ai_service.set_strategy(StrategyRegistry.get_strategy("deepseek"))

        # Enqueue the LLM job in Redis
        job_data = {
            "type": "tldr",
            "chat_id": chat_id,
            "user_id": user.id if user else None,
            "prompt": summary_prompt,
            "num_messages": num_messages,
            "original_messages": messages_list,
        }
        await self.redis_queue.enqueue(job_data)

        # Optionally: store job info in context for tracking
        if not hasattr(context, "chat_data") or context.chat_data is None:
            context.chat_data = {}
        context.chat_data['pending_tldr'] = True

    async def switch_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # --- Analytics logging ---
        user = update.effective_user
        chat = update.effective_chat
        if user is not None and chat is not None:
            log_user_event(
                user_id=user.id,
                chat_id=chat.id,
                event_type="switch_model_command",
                username=getattr(user, "username", None),
                first_name=getattr(user, "first_name", None),
                last_name=getattr(user, "last_name", None),
                llm_name=self.ai_service.get_current_model(),
            )
        # --- End analytics logging ---

        # Defensive: check if update.message exists before calling reply_text
        async def safe_reply(text):
            if update.message:
                return await update.message.reply_text(text)
            elif update.effective_chat:
                # Fallback: send message to chat if possible
                return await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            else:
                logger.warning("No message or chat found in update for switch_model.")
                return None

        if not context.args or len(context.args) < 1 or not isinstance(context.args[0], str):
            await safe_reply("Please provide a model name.")
            return

        new_model = context.args[0].lower()

        available_models = StrategyRegistry.available_strategies()
        if new_model not in available_models:
            await safe_reply(f"Invalid model name. Available models: {', '.join(available_models)}")
            return

        # Save user model selection
        if user is not None:
            self.user_selected_model[user.id] = new_model

        try:
            # Use user's key if available
            strategy = self._get_user_strategy(user.id if user is not None else 0, new_model)
            self.ai_service.set_strategy(strategy)
            await safe_reply(f"Model switched to {new_model}")

        except Exception as e:
            logger.error(f"Error switching model: {str(e)}")
            await safe_reply(f"Failed to switch model: {str(e)}")

    async def set_api_key(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Allow user to set their own API key for a provider."""
        user = update.effective_user
        if user is None or update.message is None:
            return
        args = context.args
        if not args or len(args) != 2:
            await update.message.reply_text("Usage: /set_api_key <provider> <key>")
            return
        provider, key = args
        provider = provider.lower()
        available_models = StrategyRegistry.available_strategies()
        if provider not in available_models:
            await update.message.reply_text(
                f"❗ Invalid provider '{provider}'.\n"
                f"Please use one of: {', '.join(f'`{m}`' for m in available_models)}\n"
                "You can also use /list_providers to see all valid options."
            )
            return
        set_user_api_key(user.id, provider, key)
        await update.message.reply_text(f"API key for {provider} set successfully! Future requests will use your key.")

    async def clear_api_key(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Allow user to clear their API key for a provider."""
        user = update.effective_user
        if user is None or update.message is None:
            return
        args = context.args
        if not args or len(args) != 1:
            await update.message.reply_text("Usage: /clear_api_key <provider>")
            return
        provider = args[0].lower()
        available_models = StrategyRegistry.available_strategies()
        if provider not in available_models:
            await update.message.reply_text(
                f"❗ Invalid provider '{provider}'.\n"
                f"Please use one of: {', '.join(f'`{m}`' for m in available_models)}\n"
                "You can also use /list_providers to see all valid options."
            )
            return
        clear_user_api_key(user.id, provider)
        await update.message.reply_text(f"API key for {provider} cleared. The bot will use the default key.")

    async def list_providers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all valid provider names."""
        available_providers = StrategyRegistry.available_strategies()
        providers_text = "Valid provider names:\n" + "\n".join([f"• `{provider}`" for provider in available_providers])
        
        if update.message:
            await update.message.reply_text(providers_text, parse_mode="Markdown")
        else:
            logger.warning("No message found in update for list_providers.")

    async def upgrade_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /upgrade command to show payment link for premium subscription."""
        try:
            user_id = update.effective_user.id
            
            # Import here to avoid circular imports  
            from services.stripe_service import StripeService
            stripe_service = StripeService()
            
            base_payment_link = stripe_service.get_payment_link()
            if not base_payment_link:
                await update.message.reply_text(
                    "Payment system is not configured. Please contact support.",
                    disable_web_page_preview=True
                )
                return
            
            # Add client_reference_id URL parameter with telegram_id
            payment_link_with_id = f"{base_payment_link}?client_reference_id={user_id}"
            
            # message = (
            #     "🚀 **Upgrade to Premium!**\n\n"
            #     "✨ **Unlimited** AI conversations\n"
            #     "⚡ **Priority** processing\n" 
            #     "🎯 **Advanced** models access\n"
            #     "📊 **Detailed** usage analytics\n\n"
            #     f"Click here to upgrade: {payment_link_with_id}\n\n"
            #     "_Payment powered by Stripe 🔒_"
            # )
            message = (
                "🚀 **Upgrade to Premium!**\n\n"
                "*Current limitations (Free Plan)*\n"
                "• 5 summaries per day\n"
                "• 100 summaries per month\n"
                "• 3 group chats maximum\n\n"
                "*Premium Features*\n"
                "• ∞ Unlimited daily summaries\n"
                "• ∞ Unlimited monthly summaries\n"
                "• ∞ Unlimited group chats\n"
                "• Priority support\n\n"
                "*Price: $5/month\n\n"
                "Click the button below to upgrade:\n\n"
            )

            
            await update.message.reply_text(
                message,
                # parse_mode="Markdown", fix this later
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 Subscribe $5/mo", url=payment_link_with_id)]
                ]),
                disable_web_page_preview=True
            )
            
            # Log the upgrade attempt for analytics
            from utils.analytics_storage import log_user_event
            log_user_event(
                user_id=user_id,
                chat_id=update.effective_chat.id,
                event_type="upgrade_link_generated",
                extra=f"Payment link generated with client_reference_id: {user_id}"
            )
            
        except Exception as e:
            logger.error(f"Error in upgrade command: {e}")
            await update.message.reply_text(
                "Sorry, there was an error generating the payment link. Please try again later.",
                disable_web_page_preview=True
            )

    async def usage_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /usage command to show current usage statistics."""
        user = update.effective_user
        chat = update.effective_chat
        
        if user is not None and chat is not None:
            log_user_event(
                user_id=user.id,
                chat_id=chat.id,
                event_type="usage_command",
                username=getattr(user, "username", None),
                first_name=getattr(user, "first_name", None),
                last_name=getattr(user, "last_name", None),
            )
        
        if not user:
            return
            
        try:
            usage_string = await self.usage_service.format_usage_string(user.id)
            usage_message = f"📊 *Your Usage Statistics*\n\n{usage_string}"
            
            if not is_premium(user.id):
                usage_message += "\n\nUpgrade to Premium for unlimited access: /upgrade"
            
            if update.message:
                await update.message.reply_text(usage_message, parse_mode="Markdown")
                
        except Exception as e:
            logger.error(f"Error getting usage stats for user {user.id}: {e}")
            error_message = "Sorry, I couldn't retrieve your usage statistics at the moment. Please try again later."
            if update.message:
                await update.message.reply_text(error_message)

    async def cancel_subscription_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel_subscription command - show confirmation dialog first."""
        user = update.effective_user
        chat = update.effective_chat
        
        if user is not None and chat is not None:
            log_user_event(
                user_id=user.id,
                chat_id=chat.id,
                event_type="cancel_subscription_command",
                username=getattr(user, "username", None),
                first_name=getattr(user, "first_name", None),
                last_name=getattr(user, "last_name", None),
            )
        
        if not user or not update.message:
            return
        
        # Check if user actually has a premium subscription to cancel
        try:
            from utils.user_management import is_premium
            if not is_premium(user.id):
                await update.message.reply_text(
                    "❌ You don't have an active premium subscription to cancel.",
                    parse_mode="Markdown"
                )
                return
        except Exception as e:
            logger.error(f"Error checking premium status for user {user.id}: {e}")
            await update.message.reply_text(
                "Sorry, there was an error checking your subscription status. Please try again later.",
                parse_mode="Markdown"
            )
            return
        
        # Show confirmation dialog
        confirmation_message = (
            "⚠️ *Cancel Premium Subscription?*\n\n"
            "Are you sure you want to cancel your premium subscription?\n\n"
            "• You'll keep premium access until the end of your current billing period\n"
            "• After that, you'll return to the free plan (5 summaries/day)\n"
            "• You can reactivate anytime before the period ends\n\n"
            "*This action can be undone before your subscription expires.*"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, Cancel", callback_data=f"cancel_sub_confirm_{user.id}"),
                InlineKeyboardButton("❌ No, Keep It", callback_data=f"cancel_sub_abort_{user.id}")
            ]
        ])
        
        await update.message.reply_text(
            confirmation_message,
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    async def handle_cancel_subscription_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the confirmation callback for subscription cancellation."""
        query = update.callback_query
        if not query or not query.data:
            return
        
        await query.answer()  # Acknowledge the callback
        
        user = update.effective_user
        if not user:
            return
        
        # Parse callback data
        if query.data.startswith("cancel_sub_confirm_"):
            user_id_from_callback = query.data.split("_")[-1]
            
            # Security check: ensure user can only cancel their own subscription
            if str(user.id) != user_id_from_callback:
                await query.edit_message_text(
                    "❌ You can only cancel your own subscription.",
                    parse_mode="Markdown"
                )
                return
            
            # Show processing message
            await query.edit_message_text(
                "⏳ Processing cancellation...",
                parse_mode="Markdown"
            )
            
            try:
                # Actually cancel the subscription
                result = await self.stripe_service.cancel_subscription_by_telegram_id(user.id)
                
                # Don't send immediate response - let webhook handle the notification
                if result["success"]:
                    await query.edit_message_text(
                        "⏳ Cancellation processed. You'll receive a confirmation shortly.",
                        parse_mode="Markdown"
                    )
                    
                    # Log successful cancellation
                    log_user_event(
                        user_id=user.id,
                        chat_id=query.message.chat_id if query.message else 0,
                        event_type="subscription_cancelled_by_user",
                        username=getattr(user, "username", None),
                        first_name=getattr(user, "first_name", None),
                        last_name=getattr(user, "last_name", None),
                    )
                else:
                    await query.edit_message_text(
                        f"❌ {result['message']}",
                        parse_mode="Markdown"
                    )
                    
            except Exception as e:
                logger.error(f"Error cancelling subscription for user {user.id}: {e}")
                await query.edit_message_text(
                    "❌ Sorry, there was an error processing your cancellation. Please try again later.",
                    parse_mode="Markdown"
                )
        
        elif query.data.startswith("cancel_sub_abort_"):
            # User decided not to cancel
            await query.edit_message_text(
                "✅ Subscription cancellation aborted. Your premium subscription remains active.",
                parse_mode="Markdown"
            )

    async def _block_and_dm(self, telegram_id: int, update: Update):
        """Block over-quota command and send DM to user with upgrade CTA."""
        try:
            # Delete the command message in group if possible
            if update.message and update.effective_chat and update.effective_chat.type in ['group', 'supergroup']:
                try:
                    await update.message.delete()
                    logger.info(f"Deleted over-quota command from group {update.effective_chat.id}")
                except Exception as e:
                    logger.warning(f"Could not delete over-quota message: {e}")
            
            # Check DM throttling
            can_dm = await self.usage_service.quota_manager.can_send_dm(telegram_id)
            
            if can_dm:
                # Send DM to user
                dm_message = (
                    "🔒 *Free limit reached (5/day)*\n\n"
                    "Upgrade for unlimited summaries and features!"
                )
                
                # Add user to pending purchases for auto-linking
                self.stripe_service.add_pending_purchase(telegram_id)
                
                payment_link = self.stripe_service.get_payment_link()
                if payment_link:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("💳 Subscribe $5/mo", url=payment_link)]
                    ])
                    
                    try:
                        await update.get_bot().send_message(
                            chat_id=telegram_id,
                            text=dm_message,
                            parse_mode="Markdown",
                            reply_markup=keyboard
                        )
                        
                        # Mark DM as sent to activate throttling
                        await self.usage_service.quota_manager.mark_dm_sent(telegram_id)
                        
                        # Log the limit hit and DM sent
                        log_user_event(
                            user_id=telegram_id,
                            chat_id=update.effective_chat.id if update.effective_chat else 0,
                            event_type="limit_hit_dm_sent",
                            extra="User hit quota limit, DM sent with upgrade CTA"
                        )
                        
                        logger.info(f"Sent quota limit DM to user {telegram_id}")
                        
                    except Exception as e:
                        logger.error(f"Failed to send DM to user {telegram_id}: {e}")
                        # Fallback: reply in group (but only once per 15 min)
                        await self._fallback_group_reply(update)
                else:
                    logger.error("No payment link available for quota limit DM")
            else:
                logger.info(f"DM throttled for user {telegram_id}, not sending quota limit message")
                
        except Exception as e:
            logger.error(f"Error in block_and_dm for user {telegram_id}: {e}")

    async def _fallback_group_reply(self, update: Update):
        """Fallback reply in group when DM fails."""
        try:
            if update.message:
                fallback_message = (
                    "🔒 You've reached your daily summary limit. "
                    "Send me a private message with /upgrade for unlimited access."
                )
                await update.message.reply_text(fallback_message)
        except Exception as e:
            logger.error(f"Error in fallback group reply: {e}")

    async def inline_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline queries."""
        if not hasattr(update, "inline_query") or update.inline_query is None:
            # Defensive: log and return if inline_query is missing
            logger.warning("No inline_query found in update for inline_query handler.")
            return

        query = getattr(update.inline_query, "query", "")
        results = [
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="Summarize Conversation",
                input_message_content=InputTextMessageContent(f"/tldr"),
                description="Summarize the conversation in the group chat",
            ),
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="Start",
                input_message_content=InputTextMessageContent(f"/start"),
                description="Start the bot",
            ),
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="Help",
                input_message_content=InputTextMessageContent(f"/help"),
                description="Display help information",
            ),
        ]

        if hasattr(update.inline_query, "answer") and callable(update.inline_query.answer):
            await update.inline_query.answer(results)
        else:
            logger.warning("inline_query.answer is not available on update.inline_query.")

    @staticmethod
    def _parse_message_count(args, default: int, max_limit: int) -> int:
        if not args:
            return default
        try:
            count = int(args[0])
            return min(max(count, 1), max_limit)
        except ValueError:
            return default

    def _create_summary_prompt(self, text: str) -> str:
        return (f"{text}\nBased on the above, output the following\n\n"
                "Summary: [4-5 Sentences]\n\n"
                "Sentiment: [Choose between, Positive, Negative, Neutral]\n\n"
                "Events: [List Date, Time and Nature of any upcoming events if there are any]")

    def _format_summary(self, summary: str, user_name: str, message_count: int) -> str:
        return TextProcessor.format_summary_message(summary, user_name, message_count)

    # --- Bill Splitting Conversation Handlers ---

    async def split_bill_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # --- Analytics logging ---
        user = update.effective_user
        chat = update.effective_chat
        if user is not None and chat is not None:
            log_user_event(
                user_id=user.id,
                chat_id=chat.id,
                event_type="split_bill_start",
                username=getattr(user, "username", None),
                first_name=getattr(user, "first_name", None),
                last_name=getattr(user, "last_name", None),
                llm_name=self.ai_service.get_current_model(),
            )
        # --- End analytics logging ---

        """
        Entry point for bill splitting: ask user to send receipt photo with caption.
        """
        # Defensive: check if update.message exists before calling reply_text
        if update.message:
            await update.message.reply_text(
                "To split a bill, send a photo of the receipt *with a caption* describing who paid for what.\n\n"
                "Example caption:\n"
                "Alice: Burger, Fries\n"
                "Bob: Salad\n"
                "Shared: Drinks\n\n"
                "(Make sure item names in your caption roughly match the receipt.)",
                parse_mode="Markdown"
            )
        else:
            # Fallback: send message to chat if possible
            if update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=(
                        "To split a bill, send a photo of the receipt *with a caption* describing who paid for what.\n\n"
                        "Example caption:\n"
                        "Alice: Burger, Fries\n"
                        "Bob: Salad\n"
                        "Shared: Drinks\n\n"
                        "(Make sure item names in your caption roughly match the receipt.)"
                    ),
                    parse_mode="Markdown"
                )
        return RECEIPT_IMAGE

    async def split_bill_photo_with_context(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Defensive: check if update.message exists before accessing its attributes
        message = getattr(update, "message", None)
        if not message or not getattr(message, "photo", None) or not getattr(message, "caption", None):
            # Defensive: reply in the right place
            if message and hasattr(message, "reply_text"):
                await message.reply_text(
                    "Please send a *photo of the receipt* with a *caption* describing who paid for what.",
                    parse_mode="Markdown"
                )
            elif update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Please send a *photo of the receipt* with a *caption* describing who paid for what.",
                    parse_mode="Markdown"
                )
            return RECEIPT_IMAGE

        # FREEMIUM: Check quota before processing (bill splitting uses AI services)
        user = update.effective_user
        chat_id = update.effective_chat.id if update.effective_chat else 0
        
        if user:
            try:
                # Track performance for quota checks
                quota_start_time = time.time()
                
                # Check if user is within quota
                within_quota = await self.usage_service.within_quota(user.id, chat_id)
                
                # Log performance metrics
                quota_end_time = time.time()
                quota_duration = (quota_end_time - quota_start_time) * 1000  # Convert to ms
                
                if quota_duration > 50:  # Log if quota check took longer than 50ms
                    logger.warning(f"Quota check took {quota_duration:.2f}ms for user {user.id}")
                else:
                    logger.debug(f"Quota check completed in {quota_duration:.2f}ms for user {user.id}")
                
                if not within_quota:
                    # Block the command and send DM
                    await self._block_and_dm(user.id, update)
                    return ConversationHandler.END
                    
            except Exception as e:
                logger.error(f"Error checking quota for bill split user {user.id}: {e}")
                # Fail-safe: allow premium users, block others
                if not is_premium(user.id):
                    if message and hasattr(message, "reply_text"):
                        await message.reply_text("Service temporarily unavailable. Please try again later.")
                    elif update.effective_chat:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text="Service temporarily unavailable. Please try again later."
                        )
                    return ConversationHandler.END

        photo_file = await message.photo[-1].get_file()
        image_stream = BytesIO()
        await photo_file.download_to_memory(image_stream)
        image_stream.seek(0)
        image_bytes = image_stream.read()
        user_context_text = message.caption

        # Defensive: reply in the right place
        if hasattr(message, "reply_text"):
            await message.reply_text("Processing receipt and context...")
        elif update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Processing receipt and context..."
            )

        # FREEMIUM: Increment usage counters for successful requests
        if user:
            try:
                counters = await self.usage_service.increment_counters(user.id, chat_id)
                logger.info(f"Updated usage counters for bill split user {user.id}: {counters}")
            except Exception as e:
                logger.error(f"Error incrementing counters for bill split user {user.id}: {e}")

        # 2. Extract receipt data
        receipt_data = await extract_receipt_data_from_image(image_bytes)
        if not receipt_data:
            if hasattr(message, "reply_text"):
                await message.reply_text(
                    "Sorry, I couldn't extract data from that receipt. Please try again with a clearer image."
                )
            elif update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Sorry, I couldn't extract data from that receipt. Please try again with a clearer image."
                )
            return RECEIPT_IMAGE

        # 3. Parse context and prepare confirmation
        parsing_result = parse_payment_context_with_llm(
            user_context_text,
            receipt_data.items,
            self.ai_service
        )

        # Handle parsing errors (returns error message string)
        if isinstance(parsing_result, str):
            if hasattr(message, "reply_text"):
                await message.reply_text(
                    f"Context Parsing Failed: {parsing_result}\nPlease try again with a clearer caption."
                )
            elif update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Context Parsing Failed: {parsing_result}\nPlease try again with a clearer caption."
                )
            return RECEIPT_IMAGE

        # Unpack parsing results
        assignments, shared_items, participants = parsing_result

        # Defensive: ensure context.user_data is a dict
        if not hasattr(context, "user_data") or context.user_data is None:
            context.user_data = {}

        # Store intermediate data for confirmation
        context.user_data['bill_split'] = {
            'receipt_data': receipt_data,
            'assignments': assignments,
            'shared_items': shared_items,
            'participants': participants,
        }

        # Build confirmation summary
        lines = ["I've parsed your receipt as follows:"]
        # Assigned items per person
        for person, items in assignments.items():
            item_names = ", ".join(item.name for item in items)
            lines.append(f"- {person}: {item_names}")
        # Shared items
        if shared_items:
            shared_names = ", ".join(item.name for item in shared_items)
            lines.append(f"- Shared: {shared_names}")
        # Participants
        if participants:
            parts = ", ".join(participants)
            lines.append(f"Participants: {parts}")
        lines.append("\nPlease reply with 'confirm' to finalize the split, or /cancel to abort.")

        # Defensive: reply in the right place
        if hasattr(message, "reply_text"):
            await message.reply_text("\n".join(lines))
        elif update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="\n".join(lines)
            )
        return CONFIRMATION

    async def split_bill_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Finalize bill split after user confirmation.
        """
        # Defensive: ensure context.user_data is a dict
        if not hasattr(context, "user_data") or context.user_data is None:
            context.user_data = {}

        data = context.user_data.get('bill_split') if isinstance(context.user_data, dict) else None

        # Defensive: get message object
        message = getattr(update, "message", None)

        if not data:
            # Defensive: reply in the right place
            if message and hasattr(message, "reply_text"):
                await message.reply_text(
                    "No active bill-splitting operation. Please use /splitbill to start."
                )
            elif update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="No active bill-splitting operation. Please use /splitbill to start."
                )
            return ConversationHandler.END

        receipt_data = data['receipt_data']
        assignments = data['assignments']
        shared_items = data['shared_items']
        participants = data['participants']

        # Perform calculation
        split_result = calculate_split(
            assignments,
            shared_items,
            participants,
            receipt_data.total_amount,
            receipt_data.service_charge,
            receipt_data.tax_amount
        )
        if isinstance(split_result, str):
            if message and hasattr(message, "reply_text"):
                await message.reply_text(f"Calculation error: {split_result}")
            elif update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Calculation error: {split_result}"
                )
            if isinstance(context.user_data, dict):
                context.user_data.pop('bill_split', None)
            return ConversationHandler.END

        # Format and send final results
        final_message = format_split_results(
            split_result,
            receipt_data.total_amount,
            receipt_data.service_charge,
            receipt_data.tax_amount
        )
        if message and hasattr(message, "reply_text"):
            await message.reply_text(final_message, parse_mode="Markdown")
        elif update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=final_message,
                parse_mode="Markdown"
            )
        # Clean up
        if isinstance(context.user_data, dict):
            context.user_data.pop('bill_split', None)
        return ConversationHandler.END

    async def split_bill_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Cancel the bill-splitting flow.
        """
        # Optionally clean up any stored data
        if hasattr(context, "user_data") and isinstance(context.user_data, dict):
            context.user_data.pop('bill_split', None)
        # Defensive: reply in the right place
        message = getattr(update, "message", None)
        if message and hasattr(message, "reply_text"):
            await message.reply_text("Bill splitting cancelled.")
        elif update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Bill splitting cancelled."
            )
        return ConversationHandler.END
