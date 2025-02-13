from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from uuid import uuid4
from telegram.ext import ContextTypes
from services.ai import StrategyRegistry
from utils.memory_storage import MemoryStorage
from services.ai.ai_service import AIService
from utils.text_processor import TextProcessor
import logging
from config.settings import OpenAIConfig, GroqAIConfig
from services.pdf_service import PDFService
import os

logger = logging.getLogger(__name__)

class CommandHandlers:
    def __init__(self, memory_storage: MemoryStorage):
        self.memory_storage = memory_storage
        self.ai_service = AIService(StrategyRegistry.get_strategy("openai"))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Hello! I'm TLDR Bot. How can I help you today?")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("I'm TLDR Bot. I can summarize conversations and answer questions. Use /tldr to summarize a conversation and /help to see this message again.")

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

    async def handle_pdf(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle PDF summarization requests."""
        temp_dir = None
        try:
            # Validation checks
            if not update.message or not update.message.reply_to_message:
                await self.summarize(update, context)
                return

            if not update.message.reply_to_message.document:
                await update.message.reply_text("Please reply to a PDF document with /tldr")
                return

            document = update.message.reply_to_message.document
            if not document.file_name.lower().endswith('.pdf'):
                await update.message.reply_text("Please reply to a PDF document")
                return

            # Download and process PDF
            status_message = await update.message.reply_text("Processing PDF...")
            pdf_service = PDFService()

            pdf_path = await pdf_service.upload_to_temp(document)
            if not pdf_path:
                await status_message.edit_text("Failed to process the PDF")
                return

            await status_message.edit_text("Extracting content...")

            # Extract text content directly from PDF
            text_content = await pdf_service.extract_text(pdf_path)

            if text_content:
                # If text extraction successful, use it directly
                summary_prompt = (
                    f"Please provide a comprehensive summary of the following PDF content:\n\n"
                    f"{text_content}\n\n"
                    f"Please structure the summary as follows:\n"
                    f"1. Main Topic/Title\n"
                    f"2. Important Context on Company\n"
                    f"3. Key Questions\n"
                    f"4. Other Important Details\n"
                )

            else:
                # Fallback to image processing if text extraction fails
                image_paths, temp_dir = await pdf_service.convert_pdf_to_images(pdf_path)
                if not image_paths:
                    await status_message.edit_text("Failed to process the PDF")
                    return

                # Process images in chunks concurrently
                chunk_size = 3  # Process 3 pages at a time
                all_content = []

                for i in range(0, len(image_paths), chunk_size):
                    chunk = image_paths[i:i + chunk_size]
                    tasks = []

                    for image_path in chunk:
                        tasks.append(pdf_service.process_image(image_path, self.ai_service))

                    chunk_results = await asyncio.gather(*tasks)
                    all_content.extend([r for r in chunk_results if r])

                text_content = "\n\n".join(all_content)
                summary_prompt = (
                    f"Please provide a comprehensive summary of the following PDF content:\n\n"
                    f"{text_content}\n\n"
                    f"Please structure the summary as follows:\n"
                    f"1. Main Topic/Title\n"
                    f"2. Key Points (3-5 points)\n"
                    f"3. Important Details\n"
                    f"4. Conclusion/Summary"
                )

            await status_message.edit_text("Generating summary...")
            overall_summary = self.ai_service.get_response(summary_prompt)
            formatted_summary = self._format_summary(
                overall_summary,
                update.effective_user,
                1  # Single summary
            )

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=formatted_summary,
                parse_mode="MarkdownV2",
            )
            await status_message.delete()

        except Exception as e:
            logger.error(f"Error processing PDF: {e}")
            await update.message.reply_text(f"An error occurred while processing the PDF: {str(e)}")

        finally:
            # Cleanup
            if temp_dir:
                temp_dir.cleanup()
            if 'pdf_path' in locals() and pdf_path and os.path.exists(pdf_path):
                os.remove(pdf_path)

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
