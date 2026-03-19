"""
Vision OCR client — DeepSeek-OCR-2 via Cloud.ru Foundation Models.

Sends document page images to a Vision LLM and receives structured Markdown.
Uses the same openai SDK as the rest of the project (OpenAI-compatible API).

Prompt reference (from HuggingFace model card):
  - Document mode:  <image>\\n<|grounding|>Convert the document to markdown.
  - Free OCR mode:  <image>\\nFree OCR.
We use document mode for structured output (tables, headings) and strip coordinates.
"""
import base64
import io
import re
import time
from typing import Optional

import openai
import structlog

from app.config import get_settings
from app.services.usage_tracker import track_usage, get_usage_context

logger = structlog.get_logger()

_OCR_PROMPT = "<image>\n<|grounding|>Convert the document to markdown."

_GROUNDING_CATS = (
    "text", "sub_title", "title", "table", "header", "footer",
    "figure", "caption", "list", "formula", "isolate_formula",
    "footnote", "image", "table_caption", "table_footnote",
)
_CATS_ALT = "|".join(re.escape(c) for c in _GROUNDING_CATS)

_GROUNDING_COORDS_RE = re.compile(
    r"(?:" + _CATS_ALT + r")"
    r"\[(?:\[[\d,\s]+\],?\s*)*\[[\d,\s]+\]\]\s*"
)

_GROUNDING_PREFIX_RE = re.compile(
    r"(?:" + _CATS_ALT + r")_"
)

_MAX_RETRIES = 2
_MIN_PAGE_CHARS = 5
_MAX_TOKENS = 4096


def _html_table_to_readable(text: str) -> str:
    """Reformat inline <table>...</table> from Vision OCR for LLM readability.

    Vision OCR concatenates cells without separators, so we add structural
    hints (newlines, | for colspan) rather than trying to split cells.
    """

    def _convert_one(m: re.Match) -> str:
        inner = m.group(1)
        inner = re.sub(r"<tr\s*/?>", "\n", inner)
        inner = re.sub(r"</tr>", "", inner)
        inner = re.sub(r'<td\s+colspan="?\d+"?\s*/?>', " | ", inner)
        inner = re.sub(r"</?td\s*/?>", "", inner)
        inner = re.sub(r"</?th\s*/?>", "", inner)
        inner = inner.strip()
        return "\n[TABLE_START]\n" + inner + "\n[TABLE_END]\n"

    return re.sub(r"<table>(.*?)</table>", _convert_one, text, flags=re.DOTALL)


def _clean_ocr_output(text: str) -> str:
    """Strip grounding coordinates/prefixes, convert HTML tables, normalize whitespace."""
    text = _GROUNDING_COORDS_RE.sub("", text)
    text = _GROUNDING_PREFIX_RE.sub("", text)
    text = re.sub(r"<\|/?grounding\|>", "", text)
    text = re.sub(r"<image>", "", text)
    text = _html_table_to_readable(text)

    lines = []
    for line in text.split("\n"):
        stripped = line.rstrip()
        if stripped or (lines and lines[-1] != ""):
            lines.append(stripped)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _get_ocr_client() -> openai.OpenAI:
    settings = get_settings()
    extra_headers = {}
    if settings.OCR_PROJECT_ID:
        extra_headers["x-project-id"] = settings.OCR_PROJECT_ID

    return openai.OpenAI(
        api_key=settings.OCR_API_KEY,
        base_url=settings.OCR_BASE_URL,
        default_headers=extra_headers or None,
        timeout=settings.OCR_TIMEOUT,
    )


def _detect_mime(filename: str) -> str:
    fn = filename.lower()
    if fn.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if fn.endswith(".png"):
        return "image/png"
    if fn.endswith((".tif", ".tiff")):
        return "image/tiff"
    if fn.endswith(".bmp"):
        return "image/bmp"
    return "image/png"


def _is_blank_image(pil_image) -> bool:
    """Quick check if an image is mostly blank (white/empty)."""
    from PIL import ImageStat
    stat = ImageStat.Stat(pil_image.convert("L"))
    mean_brightness = stat.mean[0]
    stddev = stat.stddev[0]
    return mean_brightness > 248 and stddev < 5


def ocr_image_to_markdown(
    image_bytes: bytes,
    filename: str = "",
    page_num: Optional[int] = None,
) -> str:
    """Send a single page image to DeepSeek-OCR-2, return clean Markdown text.

    Includes retry logic: up to _MAX_RETRIES attempts per page.
    """
    settings = get_settings()
    t0 = time.monotonic()

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    mime = _detect_mime(filename)

    client = _get_ocr_client()
    text = ""
    last_error = None

    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=settings.OCR_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _OCR_PROMPT},
                        {"type": "image_url", "image_url": {
                            "url": f"data:{mime};base64,{b64}",
                        }},
                    ],
                }],
                max_tokens=_MAX_TOKENS,
                temperature=0.0,
            )

            raw_text = response.choices[0].message.content or ""
            text = _clean_ocr_output(raw_text)

            duration_ms = int((time.monotonic() - t0) * 1000)
            ctx = get_usage_context()
            track_usage(
                response,
                operation="vision_ocr",
                model=settings.OCR_MODEL,
                provider="cloud_ru",
                declaration_id=ctx.get("declaration_id", ""),
                company_id=ctx.get("company_id", ""),
                duration_ms=duration_ms,
            )

            logger.info(
                "vision_ocr_page_done",
                filename=filename,
                page=page_num,
                chars=len(text),
                duration_ms=duration_ms,
                attempt=attempt + 1,
                input_tokens=getattr(getattr(response, "usage", None), "prompt_tokens", 0),
                output_tokens=getattr(getattr(response, "usage", None), "completion_tokens", 0),
            )
            return text

        except Exception as e:
            last_error = e
            if attempt < _MAX_RETRIES:
                wait = 2 ** attempt
                logger.warning(
                    "vision_ocr_page_retry",
                    filename=filename, page=page_num,
                    attempt=attempt + 1, error=str(e)[:200],
                    wait_sec=wait,
                )
                time.sleep(wait)
            else:
                logger.error(
                    "vision_ocr_page_failed",
                    filename=filename, page=page_num,
                    error=str(e)[:300],
                    attempts=_MAX_RETRIES + 1,
                )

    return ""


def ocr_pdf_to_markdown(file_bytes: bytes, filename: str = "") -> str:
    """Render each PDF page as image, OCR via Vision LLM, return combined Markdown.

    Optimizations:
    - Skips blank pages (saves API calls)
    - Renders at 300 DPI for better quality
    - Per-page retry with exponential backoff
    """
    import pdfplumber
    from PIL import Image

    pages_md: list[str] = []
    skipped = 0

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        total = len(pdf.pages)
        logger.info("vision_ocr_pdf_start", filename=filename, pages=total)

        for i, page in enumerate(pdf.pages):
            img_obj = page.to_image(resolution=300)
            pil_image: Image.Image = img_obj.original

            if _is_blank_image(pil_image):
                logger.debug("vision_ocr_skip_blank", filename=filename, page=i + 1)
                skipped += 1
                continue

            buf = io.BytesIO()
            pil_image.save(buf, format="PNG", optimize=True)
            page_bytes = buf.getvalue()

            page_md = ocr_image_to_markdown(page_bytes, filename=filename, page_num=i + 1)
            if page_md.strip():
                pages_md.append(page_md)

    result = "\n\n---\n\n".join(pages_md)
    logger.info(
        "vision_ocr_pdf_done",
        filename=filename,
        pages_total=total,
        pages_processed=total - skipped,
        pages_skipped=skipped,
        pages_with_text=len(pages_md),
        total_chars=len(result),
    )
    return result
