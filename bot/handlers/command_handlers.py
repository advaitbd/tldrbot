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
                "• `/tldr [number]` — Summarize the last [number] messages (default: 50)\n"
                "• `/dl [URL]` — Download TikToks, Reels, Shorts, etc. (WIP: might not work sometimes)\n"
                "• `/switch_model [model]` — Change the AI model\n"
                "\n*Available Models:*\n"
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

    async def summarize(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
            # Defensive: check for chat and message
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

            response = None
            try:
                memory_storage = self.memory_storage
                messages_list = memory_storage.get_recent_messages(chat_id, num_messages)
                combined_text = "\n".join(messages_list)
                summary = self._create_summary_prompt(combined_text)
                response = self.ai_service.get_response(summary)
                if response is None:
                    raise ValueError("AI service returned no summary response.")

                # Defensive: get user name as string
                user_name = None
                if update.effective_user:
                    user_name = getattr(update.effective_user, "full_name", None) or getattr(update.effective_user, "username", None) or str(update.effective_user)
                else:
                    user_name = "User"

                formatted_summary = self._format_summary(str(response), user_name, num_messages)

                # Defensive: ensure chat_data exists
                if not hasattr(context, "chat_data") or context.chat_data is None:
                    context.chat_data = {}

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
                fallback_text = str(response) if response is not None else "Sorry, I couldn't generate a summary."
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=fallback_text,
                    disable_web_page_preview=True,
                )

    async def switch_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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

                if not context.args:
                    await safe_reply("Please provide a model name.")
                    return

                new_model = context.args[0]

                available_models = StrategyRegistry.available_strategies()
                if new_model not in available_models:
                    await safe_reply(f"Invalid model name. Available models: {', '.join(available_models)}")
                    return

                try:
                    strategy = StrategyRegistry.get_strategy(new_model)
                    self.ai_service.set_strategy(strategy)
                    await safe_reply(f"Model switched to {new_model}")

                except Exception as e:
                    logger.error(f"Error switching model: {str(e)}")
                    await safe_reply(f"Failed to switch model: {str(e)}")

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
