import re
import unicodedata


def clean_ocr_text(text: str) -> str:
    """
    Clean OCR text: normalize unicode, remove extra whitespace.
    Minimal corrections — avoid replacing digits with letters.
    """
    if not text:
        return ""

    # Normalize unicode (NFKC form)
    text = unicodedata.normalize("NFKC", text)

    # Remove control characters except newlines and tabs
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

    # Normalize whitespace within lines (but preserve newlines)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line = re.sub(r'[ \t]+', ' ', line).strip()
        if line:
            cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)

    return text
