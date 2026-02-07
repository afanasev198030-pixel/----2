import io
import pdfplumber
import structlog

from app.utils.text_processing import clean_ocr_text

logger = structlog.get_logger()

# Try to import pytesseract (optional)
try:
    import pytesseract
    from PIL import Image
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False
    logger.info("pytesseract_not_available", msg="OCR for scanned documents disabled")


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF using pdfplumber. Fallback to OCR if available."""
    try:
        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        text = "\n".join(text_parts)

        if (not text or len(text.strip()) < 10) and HAS_TESSERACT:
            logger.info("pdf_no_text_trying_ocr")
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    try:
                        img = page.to_image(resolution=200)
                        if img:
                            ocr_text = pytesseract.image_to_string(img.original, lang='rus+eng')
                            if ocr_text:
                                text_parts.append(ocr_text)
                    except Exception as e:
                        logger.warning("ocr_page_failed", error=str(e))
            text = "\n".join(text_parts)

        return clean_ocr_text(text)
    except Exception as e:
        logger.error("pdf_extraction_failed", error=str(e))
        return ""


def extract_text_from_image(file_bytes: bytes) -> str:
    """Extract text from image using pytesseract (if available)."""
    if not HAS_TESSERACT:
        logger.warning("tesseract_not_available_for_image")
        return ""
    try:
        image = Image.open(io.BytesIO(file_bytes))
        text = pytesseract.image_to_string(image, lang='rus+eng')
        return clean_ocr_text(text)
    except Exception as e:
        logger.error("image_extraction_failed", error=str(e))
        return ""


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Determine file type and call appropriate extractor."""
    filename_lower = filename.lower()
    if filename_lower.endswith('.pdf'):
        return extract_text_from_pdf(file_bytes)
    elif filename_lower.endswith(('.jpg', '.jpeg', '.png', '.tiff', '.bmp')):
        return extract_text_from_image(file_bytes)
    else:
        logger.warning("unknown_file_type", filename=filename)
        return extract_text_from_pdf(file_bytes)
