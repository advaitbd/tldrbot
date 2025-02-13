import os
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import tempfile
import logging
import aiohttp
import asyncio
from typing import List, Tuple
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

class PDFService:
    @staticmethod
    async def convert_pdf_to_images(pdf_path: str) -> Tuple[List[str], tempfile.TemporaryDirectory]:
        """Convert PDF pages to images with optimized settings."""
        try:
            temp_dir = tempfile.TemporaryDirectory()
            # Optimize conversion settings
            images = convert_from_path(
                pdf_path,
                dpi=200,  # Lower DPI for faster processing
                thread_count=4,  # Use multiple threads
                size=(1000, None)  # Limit width to 1000px, maintain aspect ratio
            )

            image_paths = []
            for i, image in enumerate(images):
                image_path = os.path.join(temp_dir.name, f'page_{i}.jpg')
                image.save(image_path, 'JPEG', quality=85, optimize=True)
                image_paths.append(image_path)

            return image_paths, temp_dir
        except Exception as e:
            logger.error(f"Error converting PDF to images: {e}")
            return [], None

    @staticmethod
    async def extract_text(pdf_path: str) -> str:
        """Extract text directly from PDF using PyMuPDF."""
        try:
            doc = fitz.open(pdf_path)
            text_content = []

            for page in doc:
                text_content.append(page.get_text())

            doc.close()
            return "\n\n".join(text_content)
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return ""

    @staticmethod
    async def process_image(image_path: str, ai_service) -> str:
        """Process a single image and return its content."""
        try:
            # Optimize image before processing
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # Resize if too large
                if img.width > 1000:
                    ratio = 1000 / img.width
                    new_size = (1000, int(img.height * ratio))
                    img = img.resize(new_size, Image.LANCZOS)

                # Save optimized image
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                    img.save(tmp, 'JPEG', quality=85, optimize=True)
                    tmp_path = tmp.name

            # Try OCR first
            try:
                text = pytesseract.image_to_string(tmp_path)
                if text.strip():
                    return text
            except Exception:
                pass

            # Fallback to AI service if OCR fails
            return ai_service.get_image_response(tmp_path)
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return ""

    @staticmethod
    async def upload_to_temp(file) -> str | None:
        """Save the PDF file to a temporary location."""
        try:
            file_path = await file.get_file()
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                async with aiohttp.ClientSession() as session:
                    async with session.get(file_path.file_path) as response:
                        content = await response.read()
                        temp_file.write(content)
                return temp_file.name
        except Exception as e:
            logger.error(f"Error saving PDF: {e}")
            return None
