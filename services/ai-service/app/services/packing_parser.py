import re
from typing import Optional
from pydantic import BaseModel
import structlog

from app.services.ocr_service import extract_text

logger = structlog.get_logger()


class PackingListParsed(BaseModel):
    total_packages: Optional[int] = None
    package_type: Optional[str] = None
    total_gross_weight: Optional[float] = None
    total_net_weight: Optional[float] = None
    items: list[dict] = []
    confidence: float = 0.5
    raw_text: str = ""


def _to_float(value) -> Optional[float]:
    """Parse float from noisy OCR/LLM values like '4 131,2 kg'."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    s = s.replace("\xa0", " ").replace(" ", "")
    if "," in s and "." in s:
        # 4.131,2 -> 4131.2 ; 4,131.2 -> 4131.2
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except (ValueError, TypeError):
        return None


def _to_int(value) -> Optional[int]:
    v = _to_float(value)
    if v is None:
        return None
    try:
        i = int(round(v))
        return i if i > 0 else None
    except (ValueError, TypeError):
        return None


def _extract_table_weights(raw_text: str) -> tuple[Optional[float], Optional[float], Optional[int]]:
    """
    Parse PL table rows like:
    QTY CTN GW(KG) NW(KG) [CBM]
    """
    text_lower = raw_text.lower()
    has_weight_headers = (
        ("gw" in text_lower and "nw" in text_lower)
        or ("net weight" in text_lower and "gross weight" in text_lower)
        or ("нетто" in text_lower and "брутто" in text_lower)
    )
    if not has_weight_headers:
        return None, None, None

    def _valid_candidate(qty: Optional[float], ctn: Optional[int], gross: Optional[float], net: Optional[float]) -> bool:
        if qty is None or ctn is None or gross is None or net is None:
            return False
        if ctn <= 0 or ctn > 50000:
            return False
        if qty <= 0 or gross <= 0 or net <= 0:
            return False
        if gross < net:
            return False
        ratio = gross / max(net, 1e-9)
        if ratio > 5:
            return False
        if qty < ctn:
            return False
        if gross > 1_000_000 or net > 1_000_000:
            return False
        return True

    candidates: list[tuple[float, float, int]] = []
    table_started = False
    for line in raw_text.splitlines():
        line_lower = line.lower()
        if not table_started:
            has_row_header = (
                ("gw" in line_lower and "nw" in line_lower)
                or ("net weight" in line_lower and "gross weight" in line_lower)
                or ("нетто" in line_lower and "брутто" in line_lower)
            )
            has_qty_header = any(k in line_lower for k in ["qty", "q-ty", "ctn", "pack", "коли"])
            if has_row_header and has_qty_header:
                table_started = True
                continue
        if not table_started:
            continue
        # End of table block
        if any(k in line_lower for k in ["поставщик", "supplier", "директор", "signature", "подпись"]):
            break

        numbers = re.findall(r"\d+(?:[.,]\d+)?", line)
        if len(numbers) < 4:
            continue

        # Sliding windows allow skipping model numbers (e.g. 3115, F4, 55A).
        for i in range(0, len(numbers) - 3):
            qty = _to_float(numbers[i])
            ctn = _to_int(numbers[i + 1])

            # Layout A: qty, ctn, gross, net
            gross_a = _to_float(numbers[i + 2])
            net_a = _to_float(numbers[i + 3])
            if _valid_candidate(qty, ctn, gross_a, net_a):
                candidates.append((gross_a, net_a, ctn))

            # Layout B: qty, ctn, cbm, net, gross
            if i + 4 < len(numbers):
                net_b = _to_float(numbers[i + 3])
                gross_b = _to_float(numbers[i + 4])
                if _valid_candidate(qty, ctn, gross_b, net_b):
                    candidates.append((gross_b, net_b, ctn))

    if not candidates:
        return None, None, None

    # Total row is usually the one with maximal gross/net.
    gross, net, ctn = max(candidates, key=lambda x: (x[0], x[1]))
    return gross, net, ctn


def _llm_parse_pl(raw_text: str) -> dict:
    """Parse packing list using LLM (DeepSeek/OpenAI)."""
    try:
        from app.config import get_settings
        settings = get_settings()
        if not settings.has_llm:
            return {}
        from app.services.llm_client import get_llm_client, get_model
        import json
        client = get_llm_client()
        resp = client.chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": "Extract data from a packing list. Return JSON only."},
                {"role": "user", "content": f"""Extract from this packing list:
- total_packages (int)
- package_type (string)
- total_gross_weight (float, kg)
- total_net_weight (float, kg)
- country_origin (2-letter ISO code)
- items: array of {{description, quantity, gross_weight, net_weight, country_origin}}

Text:
{raw_text[:4000]}

Return ONLY valid JSON."""},
            ],
            temperature=0,
            max_tokens=4000,
        )
        text = resp.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        logger.warning("llm_pl_parse_failed", error=str(e))
        return {}


def parse(file_bytes: bytes, filename: str) -> PackingListParsed:
    """
    Parse packing list document and extract structured data.
    Uses LLM (GPT-4o) if available, falls back to regex.
    """
    try:
        raw_text = extract_text(file_bytes, filename)
        
        if not raw_text:
            logger.warning("no_text_extracted", filename=filename)
            return PackingListParsed(raw_text="", confidence=0.0)

        # Try LLM first
        llm = _llm_parse_pl(raw_text)
        logger.info("pl_llm_result", has_data=bool(llm), gross=llm.get("total_gross_weight") if llm else None, filename=filename)
        llm_gross = _to_float(llm.get("total_gross_weight")) if llm else None
        llm_net = _to_float(llm.get("total_net_weight")) if llm else None
        llm_packages = _to_int(llm.get("total_packages")) if llm else None
        if llm and (llm_gross is not None or llm_net is not None):
            logger.info("pl_parsed_by_llm", gross=llm_gross, net=llm_net, packages=llm_packages)
            items = []
            for it in llm.get("items", []):
                items.append({
                    "description": it.get("description", ""),
                    "quantity": _to_float(it.get("quantity")),
                    "gross_weight": _to_float(it.get("gross_weight")),
                    "net_weight": _to_float(it.get("net_weight")),
                    "country_origin": it.get("country_origin"),
                })
            return PackingListParsed(
                total_packages=llm_packages,
                package_type=llm.get("package_type"),
                total_gross_weight=llm_gross,
                total_net_weight=llm_net,
                items=items,
                confidence=0.92,
                raw_text=raw_text,
            )
        
        # Extract total packages
        total_packages = None
        package_patterns = [
            r'(?:Total\s+)?(?:Packages|Cartons|Boxes|Pallets|Мест|Коробок|Паллет)[\s:]*(\d+)',
            r'(\d+)\s*(?:packages?|cartons?|boxes?|pallets?|мест|коробок|паллет)',
        ]
        for pattern in package_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                try:
                    total_packages = int(match.group(1))
                    break
                except ValueError:
                    pass
        
        # Extract package type
        package_type = None
        type_keywords = {
            "carton": "Carton",
            "box": "Box",
            "pallet": "Pallet",
            "crate": "Crate",
            "коробка": "Carton",
            "паллет": "Pallet",
            "ящик": "Box",
        }
        for keyword, ptype in type_keywords.items():
            if keyword.lower() in raw_text.lower():
                package_type = ptype
                break
        
        # Extract gross weight
        total_gross_weight = None
        gross_patterns = [
            r'(?:Gross\s+Weight|Total\s+Gross|Общий\s+вес\s+брутто)[\s:]*([\d\s,\.]+)\s*(?:kg|кг|KG)',
            r'([\d\s,\.]+)\s*(?:kg|кг|KG)\s*(?:gross|брутто)',
        ]
        for pattern in gross_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                weight_str = match.group(1).replace(' ', '').replace(',', '.')
                try:
                    total_gross_weight = float(weight_str)
                    break
                except ValueError:
                    pass
        
        # Extract net weight
        total_net_weight = None
        net_patterns = [
            r'(?:Net\s+Weight|Total\s+Net|Общий\s+вес\s+нетто)[\s:]*([\d\s,\.]+)\s*(?:kg|кг|KG)',
            r'([\d\s,\.]+)\s*(?:kg|кг|KG)\s*(?:net|нетто)',
        ]
        for pattern in net_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                weight_str = match.group(1).replace(' ', '').replace(',', '.')
                try:
                    total_net_weight = float(weight_str)
                    break
                except ValueError:
                    pass

        # Table fallback: QTY / CTN / GW / NW rows
        if total_gross_weight is None or total_net_weight is None or total_packages is None:
            t_gross, t_net, t_packages = _extract_table_weights(raw_text)
            if total_gross_weight is None and t_gross is not None:
                total_gross_weight = t_gross
            if total_net_weight is None and t_net is not None:
                total_net_weight = t_net
            if total_packages is None and t_packages is not None:
                total_packages = t_packages
            if t_gross is not None or t_net is not None:
                logger.info(
                    "pl_table_weights_extracted",
                    filename=filename,
                    gross=total_gross_weight,
                    net=total_net_weight,
                    packages=total_packages,
                )
        
        # Parse items (simplified - just extract lines that look like items)
        items = []
        lines = raw_text.split('\n')
        for line in lines:
            line = line.strip()
            if len(line) > 10 and re.search(r'\d+', line):
                # Basic item extraction
                item = {"description": line}
                # Try to extract quantities/weights
                numbers = re.findall(r'\d+[.,]?\d*', line)
                if numbers:
                    item["quantity"] = numbers[0]
                items.append(item)
        
        # Calculate confidence
        fields_found = sum([
            bool(total_packages),
            bool(package_type),
            bool(total_gross_weight),
            bool(total_net_weight),
            len(items) > 0,
        ])
        confidence = min(0.9, 0.3 + (fields_found * 0.12))
        
        return PackingListParsed(
            total_packages=total_packages,
            package_type=package_type,
            total_gross_weight=total_gross_weight,
            total_net_weight=total_net_weight,
            items=items,
            confidence=confidence,
            raw_text=raw_text
        )
    except Exception as e:
        logger.error("packing_list_parsing_failed", filename=filename, error=str(e))
        return PackingListParsed(raw_text="", confidence=0.0)
