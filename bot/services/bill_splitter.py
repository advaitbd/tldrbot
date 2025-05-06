# bot/services/bill_splitter.py
import os
import base64
import json
import logging
from io import BytesIO
from typing import List, Dict, Any, Tuple, Set, Optional

from openai import OpenAI, OpenAIError
from pydantic import BaseModel, Field, ValidationError
from telegram import Update
from telegram.ext import ContextTypes

import os
import base64
import json
import logging

# Import AIService to use for context parsing LLM call
from services.ai.ai_service import AIService # Assuming this path is correct
from config.settings import OpenAIConfig # Assuming this path is correct

# Import Mistral OCR client
from mistralai import Mistral

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

# --- Data Models ---

class ReceiptItem(BaseModel):
    name: str
    quantity: int
    unit_price: float = Field(..., alias='unitPrice') # Handle potential camelCase from AI
    total_price: float = Field(..., alias='totalPrice') # Often easier to work with total price per line item

    class Config:
        populate_by_name = True # Allows using alias 'unitPrice' or field name 'unit_price'

class ReceiptData(BaseModel):
    merchant: str | None = None
    date: str | None = None  # Consider using datetime for validation/parsing later
    total_amount: float = Field(..., alias='totalAmount') # The final amount paid
    items: List[ReceiptItem]
    service_charge: Optional[float] = Field(None, alias='serviceCharge') # Optional service charge
    tax_amount: Optional[float] = Field(None, alias='taxAmount') # Optional tax (GST, VAT, Sales Tax etc.)

    class Config:
        populate_by_name = True
        extra = 'ignore' # Ignore extra fields AI might return

class BillSplitResult(BaseModel):
    person: str
    owes: float
    items: List[str] # Keep item descriptions simple for output

# --- Pydantic Model for LLM Context Parsing Response ---
class ContextParsingResult(BaseModel):
    assignments: Dict[str, List[str]] # Maps person name to list of ITEM NAMES
    shared_items: List[str] = Field(default_factory=list) # List of ITEM NAMES that are shared
    participants: List[str] # List of unique people involved

    class Config:
        extra = 'ignore' # Ignore any extra fields the LLM might add


# --- AI Extraction Logic ---
async def extract_receipt_data_from_image(image_bytes: bytes) -> ReceiptData | None:
    """
    Uses Mistral OCR API to extract text from the receipt image, then parses it into structured ReceiptData using an LLM.
    """
    mistral_api_key = os.getenv("MISTRAL_API_KEY")
    if not mistral_api_key:
        logger.error("Mistral API Key is not configured (MISTRAL_API_KEY).")
        return None

    logger.info("Starting receipt extraction using Mistral OCR.")
    import tempfile

    try:
        with Mistral(api_key=mistral_api_key) as mistral:
            logger.info("Saving image bytes to a temporary file for upload to Mistral.")
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name
            logger.info(f"Temporary file created at {tmp_path}")

            logger.info("Uploading file to Mistral for OCR processing...")
            uploaded_file = mistral.files.upload(
                file={
                    "file_name": os.path.basename(tmp_path),
                    "content": open(tmp_path, "rb"),
                },
                purpose="ocr"
            )
            logger.info(f"File uploaded to Mistral. File ID: {uploaded_file.id}")

            signed_url = mistral.files.get_signed_url(file_id=uploaded_file.id)
            logger.info(f"Obtained signed URL for OCR: {signed_url.url}")

            logger.info("Requesting OCR processing from Mistral using signed URL...")
            res = mistral.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "image_url",
                    "image_url": signed_url.url,
                }
            )
            logger.info("OCR request sent to Mistral. Awaiting response...")

            # Extract the OCR text from the first page's markdown
            ocr_text = ""
            if hasattr(res, "pages") and res.pages:
                logger.info(f"Mistral OCR returned {len(res.pages)} page(s). Extracting markdown from first page.")
                ocr_text = res.pages[0].markdown
                logger.debug(f"OCR Markdown (first 500 chars): {ocr_text[:500]}")
            else:
                logger.error("Mistral OCR did not return any pages.")
                return None
    except Exception as e:
        logger.error(f"Mistral OCR error: {e}")
        return None

    if not ocr_text.strip():
        logger.error("Mistral OCR returned empty text.")
        return None

    # Step 2: Use LLM to parse OCR text into ReceiptData structure
    try:
        schema_dict = ReceiptData.model_json_schema()
        schema_json_string = json.dumps(schema_dict, indent=2)
    except Exception as e:
        logger.error(f"Failed to generate schema for ReceiptData: {e}")
        return None

    logger.info("Parsing OCR text to structured ReceiptData using LLM (deepseek strategy).")
    # Use OpenAI or another LLM to structure the OCR text (reuse existing LLM logic)
    try:
        from services.ai import StrategyRegistry
        from services.ai.ai_service import AIService
        ai_service = AIService(StrategyRegistry.get_strategy("deepseek"))

        prompt = (
            f"The following is the raw OCR text from a receipt image:\n"
            f"--- OCR TEXT START ---\n"
            f"{ocr_text}\n"
            f"--- OCR TEXT END ---\n\n"
            f"Extract structured data from the above OCR text. Provide the response as a JSON object "
            f"matching the following Pydantic model schema:\n"
            f"{schema_json_string}\n\n"
            f"Key Extraction Points:\n"
            f"- 'items': Ensure this list includes name, quantity, unitPrice, and totalPrice for each line item. "
            f"Calculate totalPrice (quantity * unitPrice) if not explicitly present per item.\n"
            f"- 'totalAmount': This MUST be the final, total amount paid as shown on the receipt.\n"
            f"- 'serviceCharge': If a separate line item for service charge exists, extract its value here. "
            f"If not present, omit this field or set to null.\n"
            f"- 'taxAmount': If a separate line item for tax (like GST, VAT, Sales Tax) exists, extract its value here. "
            f"Sum multiple taxes if necessary into this single field. If no explicit tax line item is present, omit this field or set to null. "
            f"It's important to distinguish tax from service charge.\n"
            f"- Identify 'merchant' name and 'date' if available.\n"
            f"Respond ONLY with the JSON object, no explanation."
        )

        logger.debug(f"Sending prompt to LLM for structuring OCR text (first 500 chars of OCR text): {ocr_text[:500]}")
        llm_response = ai_service.get_response(prompt)
        logger.info("Received response from LLM for OCR structuring.")

        # Remove markdown code block if present
        llm_response_str = llm_response.strip()
        if llm_response_str.startswith("```json"):
            llm_response_str = llm_response_str[7:-3].strip()
        elif llm_response_str.startswith("```"):
            llm_response_str = llm_response_str[3:-3].strip()

        extracted_json = json.loads(llm_response_str)
        logger.info(f"Raw JSON extracted from LLM: {json.dumps(extracted_json, indent=2)}")

        # Validate and parse the JSON data using Pydantic
        receipt_data = ReceiptData.model_validate(extracted_json)
        logger.info("Successfully parsed ReceiptData from OCR text.")
        return receipt_data

    except Exception as e:
        logger.error(f"Error parsing OCR text to ReceiptData: {e}")
        return None

# --- LLM-based Context Parsing Logic ---

def parse_payment_context_with_llm(
    context_text: str,
    receipt_items: List[ReceiptItem],
    ai_service: AIService # Pass the AI service instance
) -> Tuple[Dict[str, List[ReceiptItem]], List[ReceiptItem], Set[str]] | str: # Return error message string on failure
    """
    Uses an LLM via AIService to parse user context and map items.
    Returns:
        - Dict mapping person name to their list of ReceiptItem objects.
        - List of ReceiptItem objects marked as shared.
        - Set of all unique people involved.
    Returns an error message string if parsing fails.
    """
    item_details_list = [f"'{item.name}' (Price: {item.total_price:.2f})" for item in receipt_items]
    item_list_str = "\n".join(f"- {detail}" for detail in item_details_list)

    try:
        parsing_schema_dict = ContextParsingResult.model_json_schema()
        parsing_schema_json_string = json.dumps(parsing_schema_dict, indent=2)
    except Exception as e:
        logger.error(f"Failed to generate schema for ContextParsingResult: {e}")
        return "Internal error: Could not generate context parsing schema."


    prompt = f"""
    User context regarding bill splitting:
    --- USER CONTEXT START ---
    {context_text}
    --- USER CONTEXT END ---

    Receipt items extracted:
    --- RECEIPT ITEMS START ---
    {item_list_str}
    --- RECEIPT ITEMS END ---

    Your task is to analyze the user context and determine:
    1.  Which person is associated with which receipt items.
    2.  Which receipt items are shared among all participants.
    3.  A list of all unique participants mentioned or implied.

    Instructions:
    - Match the item names from the user context to the names in the "Receipt items extracted" list as closely as possible. Use the *exact* item names from the receipt list in your output.
    - If the user context is unclear or ambiguous for an item, assume it is shared amongst all identified participants. If no participants are identified, you can list items under 'shared_items'.
    - If the user mentions people but doesn't assign items, include them in the participants list.
    - If no specific people are mentioned but shared items exist, the 'participants' list might be empty initially.

    Output the result as a single JSON object matching this Pydantic schema:
    --- JSON SCHEMA START ---
    {parsing_schema_json_string}
    --- JSON SCHEMA END ---

    Ensure the output is ONLY the JSON object, with no explanations before or after it.
    Use the exact item names from the provided 'Receipt items extracted' list in the 'assignments' and 'shared_items' lists within the JSON.
    """

    logger.info(f"Sending context parsing prompt to LLM ({ai_service.get_current_model()})...")
    # logger.debug(f"Context parsing prompt:\n{prompt}") # Optional

    llm_response_str = ai_service.get_response(prompt)

    if not llm_response_str:
        logger.error("LLM did not return a response for context parsing.")
        return "Error: AI service failed to provide a response for context parsing."

    logger.info("Received context parsing response from LLM.")
    # logger.debug(f"LLM Raw Response:\n{llm_response_str}") # Optional

    parsing_result: ContextParsingResult
    parsed_json : Dict[str, Any] = {}

    try:
        # Clean potential markdown code blocks
        processed_response_str = llm_response_str.strip()
        if processed_response_str.startswith("```json"):
            processed_response_str = processed_response_str[7:-3].strip()
        elif processed_response_str.startswith("```"):
             processed_response_str = processed_response_str[3:-3].strip()

        parsed_json = json.loads(processed_response_str)
        parsing_result = ContextParsingResult.model_validate(parsed_json)

        logger.info(f"Successfully parsed LLM context response: {parsing_result.model_dump()}")

        # --- Map item names back to ReceiptItem objects ---
        final_assignments: Dict[str, List[ReceiptItem]] = {}
        final_shared_items: List[ReceiptItem] = []
        processed_item_names: Set[str] = set()

        item_lookup: Dict[str, ReceiptItem] = {item.name.lower(): item for item in receipt_items}

        # Process assigned items
        for person, item_names in parsing_result.assignments.items():
            assigned_items_for_person: List[ReceiptItem] = []
            for name in item_names:
                item = item_lookup.get(name.lower())
                item_name_lower = name.lower()

                if item and item_name_lower not in processed_item_names:
                    assigned_items_for_person.append(item)
                    processed_item_names.add(item_name_lower)
                elif item_name_lower in processed_item_names:
                     logger.warning(f"Item '{name}' assigned to '{person}' but already processed. Skipping duplicate.")
                else:
                    logger.warning(f"LLM assigned item '{name}' to '{person}', but it was not found in receipt items. Skipping.")
            if assigned_items_for_person:
                 final_assignments[person] = assigned_items_for_person

        # Process shared items
        for name in parsing_result.shared_items:
            item = item_lookup.get(name.lower())
            item_name_lower = name.lower()

            if item and item_name_lower not in processed_item_names:
                final_shared_items.append(item)
                processed_item_names.add(item_name_lower)
            elif item_name_lower in processed_item_names:
                logger.warning(f"Item '{name}' listed as shared but already processed. Skipping duplicate.")
            else:
                logger.warning(f"LLM listed item '{name}' as shared, but it was not found in receipt items. Skipping.")

        # Handle items missed by the LLM - Default to shared if participants exist
        original_item_names_lower = {item.name.lower() for item in receipt_items}
        unprocessed_items_lower = original_item_names_lower - processed_item_names
        if unprocessed_items_lower:
             unprocessed_original_names = [item.name for item in receipt_items if item.name.lower() in unprocessed_items_lower]
             logger.warning(f"LLM did not process: {unprocessed_original_names}.")
             if parsing_result.participants:
                 logger.info("Defaulting unprocessed items to shared.")
                 for name_lower in unprocessed_items_lower:
                      item = item_lookup.get(name_lower)
                      if item:
                          final_shared_items.append(item)
                          processed_item_names.add(name_lower) # Mark as processed now
             else:
                 logger.warning("No participants identified, leaving unprocessed items unassigned.")


        final_participants = set(parsing_result.participants)
        # Ensure all people with assignments are included in participants
        final_participants.update(final_assignments.keys())

        if not final_participants and (final_assignments or final_shared_items):
            logger.warning("Items were assigned/shared, but the LLM didn't identify any participants. Calculation may need manual participant input.")
            # Consider returning an error or letting calculate_split handle it.

        logger.info(f"Mapped Context - Assignments: { {p: [i.name for i in items] for p, items in final_assignments.items()} }")
        logger.info(f"Mapped Context - Shared Items: {[i.name for i in final_shared_items]}")
        logger.info(f"Mapped Context - Participants: {final_participants}")

        return final_assignments, final_shared_items, final_participants

    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON response from LLM for context parsing: {e}")
        logger.error(f"LLM response content was:\n{llm_response_str}")
        return "Error: AI service returned invalid JSON for context parsing."
    except ValidationError as e:
        logger.error(f"Pydantic validation error for LLM context parsing response: {e}")
        logger.error(f"Data causing validation error:\n{json.dumps(parsed_json, indent=2)}")
        return "Error: AI service returned data in an unexpected format for context parsing."
    except Exception as e:
        logger.exception("Unexpected error during LLM context parsing and mapping:")
        return "Internal error during context processing."


# --- Calculation Logic ---

def calculate_split(
    assignments: Dict[str, List[ReceiptItem]],
    shared_items: List[ReceiptItem],
    participants: Set[str],
    total_amount: float,
    service_charge: Optional[float],
    tax_amount: Optional[float]
) -> List[BillSplitResult] | str:
    """
    Calculates how much each person owes based on assigned and shared items,
    distributing service charge and tax proportionally.
    Returns a list of BillSplitResult objects or an error message string.
    """
    if not participants and shared_items:
        return "Error: Shared items exist, but no participants were identified to split amongst."
    if not participants and assignments:
         participants = set(assignments.keys())
         logger.warning(f"No participants explicitly listed, inferring from assignments: {participants}")
         if not participants :
              return "Error: Items assigned, but could not determine participants."

    if not participants:
        return "Error: No participants found to split the bill."

    num_people = len(participants)
    person_subtotals: Dict[str, float] = {p: 0.0 for p in participants} # Tracks item costs per person
    person_items_summary: Dict[str, List[str]] = {p: [] for p in participants}

    # 1. Calculate direct costs per person from assigned items
    total_items_cost = 0.0
    for person, items in assignments.items():
        if person not in person_subtotals: # Should already exist if inferred correctly
            person_subtotals[person] = 0.0
            person_items_summary[person] = []
        person_item_total = sum(item.total_price for item in items)
        person_subtotals[person] += person_item_total
        total_items_cost += person_item_total
        person_items_summary[person].extend([f"{item.name} (${item.total_price:.2f})" for item in items])

    # 2. Calculate total shared cost and add individual shares
    total_shared_cost = sum(item.total_price for item in shared_items)
    total_items_cost += total_shared_cost
    shared_item_cost_per_person = 0.0
    if num_people > 0:
        shared_item_cost_per_person = total_shared_cost / num_people
        for person in participants:
            person_subtotals[person] += shared_item_cost_per_person

    shared_item_names = [f"{item.name} (${item.total_price:.2f})" for item in shared_items]
    if shared_item_names and num_people > 0:
        shared_summary = f"Shared Items (${shared_item_cost_per_person:.2f} each)"
        # Optional: list items if not too long: f"Shared ({', '.join(shared_item_names)}): ${shared_item_cost_per_person:.2f} each"
        for person in participants:
             if person not in person_items_summary: person_items_summary[person] = []
             person_items_summary[person].append(shared_summary)

    # 3. Calculate base for distributing service charge and tax
    # This base should be the total cost of *items* only.
    distribution_base = total_items_cost
    logger.info(f"Total items cost (distribution base): {distribution_base:.2f}")

    # 4. Distribute Service Charge (if applicable)
    person_totals_after_service: Dict[str, float] = {}
    total_service_charge = service_charge or 0.0
    service_charge_per_person: Dict[str, float] = {p: 0.0 for p in participants}

    if total_service_charge > 0 and distribution_base > 0:
        logger.info(f"Distributing Service Charge: ${total_service_charge:.2f}")
        calculated_service_total = 0.0
        for person in participants:
            person_share_ratio = person_subtotals[person] / distribution_base if distribution_base > 0 else (1/num_people)
            charge_share = person_share_ratio * total_service_charge
            service_charge_per_person[person] = charge_share
            person_totals_after_service[person] = person_subtotals[person] + charge_share
            calculated_service_total += charge_share
            if person not in person_items_summary: person_items_summary[person] = []
            person_items_summary[person].append(f"Service Charge Share (${charge_share:.2f})")
        # Log difference if calculation doesn't exactly match input charge
        if abs(calculated_service_total - total_service_charge) > 0.01:
            logger.warning(f"Calculated total service charge share ({calculated_service_total:.2f}) differs slightly from input ({total_service_charge:.2f})")
    else:
         # If no service charge, the total after service is just the subtotal
         person_totals_after_service = person_subtotals.copy()


    # 5. Distribute Tax (if applicable)
    # The base for tax distribution should include the service charge.
    tax_distribution_base = distribution_base + total_service_charge
    person_totals_after_tax: Dict[str, float] = {}
    total_tax = tax_amount or 0.0
    tax_per_person: Dict[str, float] = {p: 0.0 for p in participants}

    if total_tax > 0 and tax_distribution_base > 0:
        logger.info(f"Distributing Tax: ${total_tax:.2f} (Base: {tax_distribution_base:.2f})")
        calculated_tax_total = 0.0
        for person in participants:
            # Proportion is based on their share of (items + service charge)
            person_pre_tax_total = person_totals_after_service[person]
            tax_share_ratio = person_pre_tax_total / tax_distribution_base if tax_distribution_base > 0 else (1/num_people)
            tax_share = tax_share_ratio * total_tax
            tax_per_person[person] = tax_share
            person_totals_after_tax[person] = person_pre_tax_total + tax_share
            calculated_tax_total += tax_share
            # Add tax share to summary
            if person not in person_items_summary: person_items_summary[person] = []
            person_items_summary[person].append(f"Tax Share (${tax_share:.2f})")
        if abs(calculated_tax_total - total_tax) > 0.01:
             logger.warning(f"Calculated total tax share ({calculated_tax_total:.2f}) differs slightly from input ({total_tax:.2f})")
    else:
        # If no tax, the final total is the total after service charge
        person_totals_after_tax = person_totals_after_service.copy()


    # 6. Final result generation and validation
    final_split: List[BillSplitResult] = []
    calculated_grand_total = 0.0

    for person in participants:
        final_owe_amount = round(person_totals_after_tax[person], 2)
        calculated_grand_total += final_owe_amount
        final_split.append(BillSplitResult(
            person=person,
            owes=final_owe_amount,
            items=person_items_summary.get(person, []) # Get summary safely
        ))

    # Final validation against the receipt's total_amount
    # Allow a small tolerance, e.g., 1 cent per person
    tolerance = 0.01 * num_people
    if abs(calculated_grand_total - total_amount) > tolerance:
       logger.warning(
           f"Final calculated total ({calculated_grand_total:.2f}) differs from receipt total "
           f"({total_amount:.2f}) by more than tolerance (${tolerance:.2f}). "
           "This might be due to AI extraction errors, calculation rounding, or inconsistencies in the receipt data."
       )
       # Optional: Add adjustment logic here if desired, but it's complex and might hide errors.
       # For now, just log the warning.

    # Sort results alphabetically by person name for consistent output
    final_split.sort(key=lambda x: x.person)

    return final_split


# --- Helper to format the result ---

# Need TextProcessor for escaping in format_split_results
class TextProcessor:
    @staticmethod
    def escape_markdown(text: str) -> str:
        """Escape markdown v2 special characters."""
        if not isinstance(text, str):
             text = str(text)
        escape_chars = r'_*[]()~`>#+-=|{}.!'
        return "".join(f'\\{char}' if char in escape_chars else char for char in text)

    # Removed format_summary_message as it's not directly used in this file's primary logic
    # If needed elsewhere, it should live in a more general utility module.


def format_split_results(
    split_results: List[BillSplitResult],
    receipt_total: float,
    service_charge: Optional[float],
    tax_amount: Optional[float]
    ) -> str:
    """Formats the BillSplitResult list into a user-friendly markdown string."""
    result_lines = []
    calculated_sum_check = 0.0

    if not split_results:
        return "Could not calculate the split. No results generated."

    for res in split_results:
        calculated_sum_check += res.owes
        person_name_escaped = TextProcessor.escape_markdown(res.person)
        result_lines.append(f"*{person_name_escaped} owes: ${res.owes:.2f}*")
        # Optional: Include detailed item list per person (could get long)
        # for item_detail in res.items:
        #    # Ensure item details are also escaped if they contain special chars
        #    escaped_detail = TextProcessor.escape_markdown(item_detail)
        #    result_lines.append(f"  \\- {escaped_detail}") # Using \- for list item

    output_message = "📊 *Bill Split Result:*\n\n" + "\n".join(result_lines)

    output_message += f"\n\n🧾 *Receipt Summary:*\n"
    output_message += f"  \\- *Total Amount Paid:* ${receipt_total:.2f}\n"
    if service_charge is not None and service_charge > 0:
        output_message += f"  \\- Service Charge: ${service_charge:.2f}\n"
    if tax_amount is not None and tax_amount > 0:
        output_message += f"  \\- Tax (GST/VAT etc\\.): ${tax_amount:.2f}\n"

    # Checksum validation message
    output_message += f"\n✅ Calculated Split Sum: ${calculated_sum_check:.2f}"
    # Add warning if checksum doesn't match receipt total (within tolerance)
    tolerance = 0.01 * len(split_results)
    if abs(calculated_sum_check - receipt_total) > tolerance:
        output_message += f" \\(*Warning:* Does not exactly match receipt total of ${receipt_total:.2f}\\)"

    # Disclaimer
    output_message += "\n\n_Please double\\-check the amounts\\. AI extraction and parsing might have inaccuracies\\._"

    # Escape the final message *once* if needed by the Telegram sender,
    # but here we specifically escaped parts for MarkdownV2.
    # Re-escaping the whole thing might double-escape. Assuming the caller handles final escapes if necessary.
    return output_message

# Example Usage (Conceptual - requires actual context, update, AIService etc.)
async def handle_bill_split_request(update: Update, context: ContextTypes.DEFAULT_TYPE, image_bytes: bytes, user_message: str):
    """Conceptual handler function"""
    await update.message.reply_text("Processing receipt image...")

    receipt_data = await extract_receipt_data_from_image(image_bytes)

    if not receipt_data:
        await update.message.reply_text("Sorry, I couldn't extract data from the receipt image.")
        return

    if not receipt_data.items:
        await update.message.reply_text("Could not find any items on the receipt to split.")
        return

    # Get AIService instance (assuming it's stored in bot_data or user_data)
    ai_service = context.bot_data.get("ai_service") # Example way to get it
    if not ai_service:
         await update.message.reply_text("AI Service is not available for context parsing.")
         # Fallback: Maybe ask user to assign items manually?
         # For now, just return.
         return

    await update.message.reply_text("Analyzing who paid for what based on your message...")

    parse_result = parse_payment_context_with_llm(
        context_text=user_message,
        receipt_items=receipt_data.items,
        ai_service=ai_service
    )

    if isinstance(parse_result, str): # Check if an error message string was returned
        await update.message.reply_text(f"Error during context analysis: {parse_result}")
        return

    assignments, shared_items, participants = parse_result

    # If LLM parsing failed to find participants but items exist, prompt user?
    if not participants and (assignments or shared_items):
         # This case needs specific handling - maybe ask "Who is splitting this bill?"
         await update.message.reply_text("I found items but couldn't figure out who is splitting the bill from the message. Please list the names of everyone involved.")
         # Store state and wait for user response? Or abort.
         return # Abort for now

    await update.message.reply_text("Calculating the split...")

    split_calculation = calculate_split(
        assignments=assignments,
        shared_items=shared_items,
        participants=participants,
        total_amount=receipt_data.total_amount,
        service_charge=receipt_data.service_charge,
        tax_amount=receipt_data.tax_amount
    )

    if isinstance(split_calculation, str): # Check if calculation returned an error string
        await update.message.reply_text(f"Error during calculation: {split_calculation}")
        return

    # Format and send the final result
    final_message = format_split_results(
        split_results=split_calculation,
        receipt_total=receipt_data.total_amount,
        service_charge=receipt_data.service_charge,
        tax_amount=receipt_data.tax_amount
    )

    # Ensure the Telegram sending function uses ParseMode.MARKDOWN_V2
    await update.message.reply_text(final_message, parse_mode='MarkdownV2')
