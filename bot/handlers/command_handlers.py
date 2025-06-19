# Add necessary imports
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent, PhotoSize
from uuid import uuid4
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler as TelegramCommandHandler, # Rename to avoid clash
    MessageHandler, filters
)
import os
from services.ai import StrategyRegistry
from utils.memory_storage import MemoryStorage
from services.ai.ai_service import AIService
from utils.text_processor import TextProcessor
from utils.analytics_storage import log_user_event  # <-- NEW
from utils.user.user_api_keys import set_user_api_key, get_user_api_key, clear_user_api_key, get_all_user_keys
import logging
from config.settings import OpenAIConfig, GroqAIConfig, DeepSeekAIConfig
from services.ai.openai_strategy import OpenAIStrategy
from services.ai.groq_strategy import GroqAIStrategy
from services.ai.deepseek_strategy import DeepSeekStrategy

# Allowed OpenAI models for receipt parsing
ALLOWED_RECEIPT_MODELS = [
    OpenAIConfig.MINI_MODEL,
    OpenAIConfig.O4_MODEL,
    OpenAIConfig.FOUR_ONE_MODEL,
]
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
        self.ai_service = AIService(StrategyRegistry.get_strategy("deepseek"))  # Explicitly declare ai_service
        if redis_queue is not None:
            self.redis_queue = redis_queue
        else:
            self.redis_queue = RedisQueue()
        # Optionally: track per-user model selection in memory
        self.user_selected_model = {}  # {user_id: provider_name}
        self.user_receipt_model = {}  # {user_id: openai_model_name}

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
            "    Valid providers: `openai`, `groq`, `deepseek`\n"
            "• `/list_providers` — List all valid provider names\n"
            "• `/set_receipt_model <model>` — Choose OpenAI model for receipt parsing\n"
            "\n*Available Models:*\n"
            "• `openai-mini` — GPT-4o mini\n"
            "• `openai-4o` — GPT-4o\n"
            "• `openai-4.1` — GPT-4.1 (turbo)\n"
            "• `groq` — Uses Llama 3 (8bn) hosted by groq\n"
            "• `deepseek` — DeepSeek V3\n"
            "\n*Features:*\n"
            "• Reply to my summaries with questions for more insights\n"
            "• View sentiment analysis in summaries\n"
            "• Get key events extracted from conversations\n"
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
                "openai-mini": (OpenAIConfig, OpenAIStrategy, OpenAIConfig.MINI_MODEL),
                "openai-4o": (OpenAIConfig, OpenAIStrategy, OpenAIConfig.O4_MODEL),
                "openai-4.1": (OpenAIConfig, OpenAIStrategy, OpenAIConfig.FOUR_ONE_MODEL),
                "groq": (GroqAIConfig, GroqAIStrategy),
                "deepseek": (DeepSeekAIConfig, DeepSeekStrategy),
            },
        )

    def _resolve_strategy(self, user_id: int, provider: str, config_map: dict):
        """Helper function to resolve API key and model for a given provider."""
        if provider not in config_map:
            raise ValueError(f"Unknown provider: {provider}")

        mapping = config_map[provider]
        if len(mapping) == 3:
            config_class, strategy_class, model = mapping
        else:
            config_class, strategy_class = mapping
            model = getattr(config_class, 'MODEL', '')

        # Use a shared key for all OpenAI models
        key_provider = 'openai' if provider.startswith('openai') else provider
        user_key = get_user_api_key(user_id, key_provider)
        key = user_key if user_key is not None else (config_class.API_KEY if getattr(config_class, 'API_KEY', None) is not None else "")

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
        """List all valid provider names for BYOK and model switching."""
        available_models = StrategyRegistry.available_strategies()
        msg = (
            "🗝️ *Valid Providers for BYOK and Model Switching:*\n\n"
            + "\n".join(f"• `{m}`" for m in available_models)
            + "\n\nUse these names for `/set_api_key`, `/clear_api_key`, and `/switch_model`."
        )
        if update.message:
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            logger.warning("No message found in update for list_providers.")

    async def set_receipt_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Allow user to choose which OpenAI model is used for receipt parsing."""
        user = update.effective_user
        if user is None or update.message is None:
            return

        if not context.args or len(context.args) != 1:
            await update.message.reply_text(
                f"Usage: /set_receipt_model <model>\nAvailable: {', '.join(ALLOWED_RECEIPT_MODELS)}"
            )
            return

        model_name = context.args[0]
        if model_name not in ALLOWED_RECEIPT_MODELS:
            await update.message.reply_text(
                f"Invalid model name. Choose from: {', '.join(ALLOWED_RECEIPT_MODELS)}"
            )
            return

        self.user_receipt_model[user.id] = model_name
        await update.message.reply_text(f"Receipt parsing model set to {model_name}.")

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
            await update.message.reply_text(
                f"Using OpenAI model {self.user_receipt_model.get(user.id if user is not None else 0, os.getenv('OPENAI_MODEL', OpenAIConfig.MINI_MODEL))} for receipt parsing."
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
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Using OpenAI model {self.user_receipt_model.get(user.id if user is not None else 0, os.getenv('OPENAI_MODEL', OpenAIConfig.MINI_MODEL))} for receipt parsing."
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

        photo_file = await message.photo[-1].get_file()
        image_stream = BytesIO()
        await photo_file.download_to_memory(image_stream)
        image_stream.seek(0)
        image_bytes = image_stream.read()
        user_context_text = message.caption

        # Defensive: reply in the right place
        model_name = self.user_receipt_model.get(user.id if user is not None else 0,
                                                os.getenv('OPENAI_MODEL', OpenAIConfig.MINI_MODEL))
        if hasattr(message, "reply_text"):
            await message.reply_text(f"Processing receipt and context using {model_name}...")
        elif update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Processing receipt and context using {model_name}..."
            )

        # 2. Extract receipt data
        receipt_data = await extract_receipt_data_from_image(image_bytes, model_name)
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
        lines.append("\nPlease reply with 'confirm' to finalize the split, send a new photo with caption to retry, or /cancel to abort.")

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
