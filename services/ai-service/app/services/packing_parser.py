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


def parse(file_bytes: bytes, filename: str) -> PackingListParsed:
    """
    Parse packing list document and extract structured data.
    """
    try:
        raw_text = extract_text(file_bytes, filename)
        
        if not raw_text:
            logger.warning("no_text_extracted", filename=filename)
            return PackingListParsed(raw_text="", confidence=0.0)
        
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
