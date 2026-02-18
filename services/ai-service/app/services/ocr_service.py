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


def extract_text_from_excel(file_bytes: bytes, filename: str) -> str:
    """Extract text from Excel (.xlsx/.xls). Uses openpyxl for .xlsx, xlrd for .xls."""
    filename_lower = filename.lower()

    # Old .xls format — use xlrd
    if filename_lower.endswith('.xls') and not filename_lower.endswith('.xlsx'):
        return _extract_text_xls(file_bytes, filename)

    # .xlsx format — use openpyxl
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
        text_parts = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            text_parts.append(f"--- Sheet: {sheet_name} ---")
            for row in ws.iter_rows(values_only=True):
                cells = [str(cell) if cell is not None else "" for cell in row]
                line = "\t".join(cells).strip()
                if line and line != "\t" * len(cells):
                    text_parts.append(line)
        wb.close()
        text = "\n".join(text_parts)
        logger.info("excel_extracted", filename=filename, chars=len(text), sheets=len(wb.sheetnames))
        return text
    except Exception as e:
        logger.error("xlsx_extraction_failed", filename=filename, error=str(e))
        # Fallback: try xlrd for misnamed files
        return _extract_text_xls(file_bytes, filename)


def _extract_text_xls(file_bytes: bytes, filename: str) -> str:
    """Extract text from old .xls format using xlrd."""
    try:
        import xlrd
        wb = xlrd.open_workbook(file_contents=file_bytes)
        text_parts = []
        for sheet in wb.sheets():
            text_parts.append(f"--- Sheet: {sheet.name} ---")
            for row_idx in range(sheet.nrows):
                cells = []
                for col_idx in range(sheet.ncols):
                    cell = sheet.cell(row_idx, col_idx)
                    val = cell.value
                    if val is not None and str(val).strip():
                        cells.append(str(val).strip())
                if cells:
                    text_parts.append("\t".join(cells))
        text = "\n".join(text_parts)
        logger.info("xls_extracted", filename=filename, chars=len(text), sheets=wb.nsheets)
        return text
    except ImportError:
        logger.error("xlrd_not_installed", filename=filename, msg="pip install xlrd")
        return ""
    except Exception as e:
        logger.error("xls_extraction_failed", filename=filename, error=str(e))
        return ""


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Determine file type and call appropriate extractor."""
    filename_lower = filename.lower()
    if filename_lower.endswith('.pdf'):
        return extract_text_from_pdf(file_bytes)
    elif filename_lower.endswith(('.jpg', '.jpeg', '.png', '.tiff', '.bmp')):
        return extract_text_from_image(file_bytes)
    elif filename_lower.endswith(('.xlsx', '.xls')):
        return extract_text_from_excel(file_bytes, filename)
    else:
        logger.warning("unknown_file_type", filename=filename)
        return extract_text_from_pdf(file_bytes)
