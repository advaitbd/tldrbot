# Add necessary imports
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent, PhotoSize
from uuid import uuid4
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler as TelegramCommandHandler, # Rename to avoid clash
    MessageHandler, filters
)
from services.ai import StrategyRegistry
from utils.memory_storage import MemoryStorage
from services.ai.ai_service import AIService
from utils.text_processor import TextProcessor
import logging
from config.settings import OpenAIConfig, GroqAIConfig

# Import the new bill splitting service functions
from services.bill_splitter import (
    extract_receipt_data_from_image,
    parse_payment_context_with_llm,
    calculate_split,
    format_split_results,
    ReceiptData # Import ReceiptData for type hinting if needed
)
from io import BytesIO

logger = logging.getLogger(__name__)

# Define conversation states
RECEIPT_IMAGE, CONFIRMATION = range(2)

class CommandHandlers:
    def __init__(self, memory_storage: MemoryStorage):
        self.memory_storage = memory_storage
        self.ai_service = AIService(StrategyRegistry.get_strategy("deepseek"))

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "🤖 *Welcome to TLDR Bot!* 🤖\n\n"
            "I help you summarize conversations and provide insights. Here's what I can do:\n\n"
            "*Commands:*\n"
            "• `/tldr [number]` - Summarize the last [number] messages (default: 50)\n"
            "• `/dl [URL]` - Download TikToks, Reels, Shorts, etc. (WIP: might not work sometimes)\n"
            "• `/switch_model [model]` - Change the AI model\n"
            "\n*Available Models:*\n"
            "• `groq` - Uses Llama 3 (8bn) hosted by groq\n"
            "• `deepseek` - DeepSeek V3\n"
            "\n*Features:*\n"
            "• Reply to my summaries with questions for more insights\n"
            "• View sentiment analysis in summaries\n"
            "• Get key events extracted from conversations\n"
            "\n*Current model:* " + self.ai_service.get_current_model()
        )

        await update.message.reply_text(help_text, parse_mode="Markdown")

    async def summarize(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        num_messages = self._parse_message_count(context.args, default=50, max_limit=400)

        if not num_messages:
            await update.message.reply_text("Invalid message count")
            return

        try:
            memory_storage = self.memory_storage
            messages_list = memory_storage.get_recent_messages(chat_id, num_messages)
            combined_text = "\n".join(messages_list)
            summary = self._create_summary_prompt(combined_text)
            response = self.ai_service.get_response(summary)
            formatted_summary = self._format_summary(response, update.effective_user, num_messages)

            summary_message = await context.bot.send_message(
                chat_id=chat_id,
                text=formatted_summary,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True,
            )

            # Store context for follow-up questions
            context.chat_data['summary_message_id'] = summary_message.message_id
            context.chat_data['original_messages'] = messages_list

        except Exception as e:
            logger.error(f"Message formatting error: {str(e)}")
            # Fallback to plain text if markdown parsing fails
            await context.bot.send_message(
                chat_id=chat_id,
                text=str(response),
                disable_web_page_preview=True,
            )

    async def switch_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Please provide a model name.")
            return

        new_model = context.args[0]

        available_models = StrategyRegistry.available_strategies()
        if new_model not in available_models:
            await update.message.reply_text(f"Invalid model name. Available models: {', '.join(available_models)}")
            return

        try:
            strategy = StrategyRegistry.get_strategy(new_model)
            self.ai_service.set_strategy(strategy)
            await update.message.reply_text(f"Model switched to {new_model}")

        except Exception as e:
            logger.error(f"Error switching model: {str(e)}")
            await update.message.reply_text(f"Failed to switch model: {str(e)}")

    async def inline_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline queries."""
        query = update.inline_query.query
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

        await update.inline_query.answer(results)

    @staticmethod
    def _parse_message_count(args, default: int, max_limit: int) -> int:
        if not args:
            return default
        try:
            count = int(args[0])
            return min(max(count, 1), max_limit)
        except ValueError:
            return None

    def _create_summary_prompt(self, text: str) -> str:
        return (f"{text}\nBased on the above, output the following\n\n"
                "Summary: [4-5 Sentences]\n\n"
                "Sentiment: [Choose between, Positive, Negative, Neutral]\n\n"
                "Events: [List Date, Time and Nature of any upcoming events if there are any]")

    def _format_summary(self, summary: str, user_name: str, message_count: int) -> str:
        return TextProcessor.format_summary_message(summary, user_name, message_count)

    # --- Bill Splitting Conversation Handlers ---

    async def split_bill_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Entry point for bill splitting: ask user to send receipt photo with caption.
        """
        await update.message.reply_text(
            "To split a bill, send a photo of the receipt *with a caption* describing who paid for what.\n\n"
            "Example caption:\n"
            "Alice: Burger, Fries\n"
            "Bob: Salad\n"
            "Shared: Drinks\n\n"
            "(Make sure item names in your caption roughly match the receipt.)",
            parse_mode="Markdown"
        )
        return RECEIPT_IMAGE

    async def split_bill_photo_with_context(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # 1. Check for photo and caption
        if not update.message.photo or not update.message.caption:
            await update.message.reply_text(
                "Please send a *photo of the receipt* with a *caption* describing who paid for what.",
                parse_mode="Markdown"
            )
            return

        photo_file = await update.message.photo[-1].get_file()
        image_stream = BytesIO()
        await photo_file.download_to_memory(image_stream)
        image_stream.seek(0)
        image_bytes = image_stream.read()
        user_context_text = update.message.caption

        await update.message.reply_text("Processing receipt and context...")

        # 2. Extract receipt data
        receipt_data = await extract_receipt_data_from_image(image_bytes)
        if not receipt_data:
            await update.message.reply_text(
                "Sorry, I couldn't extract data from that receipt. Please try again with a clearer image."
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
            await update.message.reply_text(
                f"Context Parsing Failed: {parsing_result}\nPlease try again with a clearer caption."
            )
            return RECEIPT_IMAGE

        # Unpack parsing results
        assignments, shared_items, participants = parsing_result

        # Store intermediate data for confirmation
        context.user_data['bill_split'] = {
            'receipt_data': receipt_data,
            'assignments': assignments,
            'shared_items': shared_items,
            'participants': participants,
        }

        # Build confirmation summary
        lines = ["I’ve parsed your receipt as follows:"]
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
        await update.message.reply_text("\n".join(lines))
        return CONFIRMATION
    
    async def split_bill_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Finalize bill split after user confirmation.
        """
        data = context.user_data.get('bill_split')
        if not data:
            await update.message.reply_text(
                "No active bill-splitting operation. Please use /splitbill to start."
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
            await update.message.reply_text(f"Calculation error: {split_result}")
            context.user_data.pop('bill_split', None)
            return ConversationHandler.END

        # Format and send final results
        final_message = format_split_results(
            split_result,
            receipt_data.total_amount,
            receipt_data.service_charge,
            receipt_data.tax_amount
        )
        await update.message.reply_text(final_message, parse_mode="Markdown")
        # Clean up
        context.user_data.pop('bill_split', None)
        return ConversationHandler.END

    async def split_bill_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Cancel the bill-splitting flow.
        """
        # Optionally clean up any stored data
        context.user_data.pop('bill_split', None)
        await update.message.reply_text("Bill splitting cancelled.")
        return ConversationHandler.END
