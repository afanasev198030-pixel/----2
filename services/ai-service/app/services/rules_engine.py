"""
Rules engine: loads declaration_mapping_v3.yaml, validates parsed results,
builds evidence_map (field → source document) and issues list.
Also fetches graph rules from core-api DB for LLM prompt enrichment.
"""
import re
import math
from pathlib import Path
from typing import Any, Optional
import structlog

logger = structlog.get_logger()

_rules: dict | None = None
_db_rules_cache: list[dict] | None = None
_strategies_cache: list[dict] | None = None


def fetch_db_rules(core_api_url: str = "http://core-api:8001") -> list[dict]:
    """Загрузить правила граф из БД core-api. Кешируются до перезапуска сервиса."""
    global _db_rules_cache
    if _db_rules_cache is not None:
        return _db_rules_cache
    try:
        import httpx
        from app.middleware.tracing import get_correlation_id
        headers = {}
        cid = get_correlation_id()
        if cid:
            headers["X-Request-ID"] = cid
        resp = httpx.get(
            f"{core_api_url}/api/v1/graph-rules/internal",
            timeout=5.0,
            params={"declaration_type": "IM40"},
            headers=headers,
        )
        if resp.status_code == 200:
            _db_rules_cache = resp.json()
            logger.info("db_rules_loaded", count=len(_db_rules_cache))
            return _db_rules_cache
        logger.warning("db_rules_bad_status", status=resp.status_code)
    except Exception as e:
        logger.warning("db_rules_fetch_failed", error=str(e))
    _db_rules_cache = []
    return []


def fetch_ai_strategies(core_api_url: str = "http://core-api:8001") -> list[dict]:
    """Загрузить активные AI-стратегии из core-api. Кешируются до перезапуска."""
    global _strategies_cache
    if _strategies_cache is not None:
        return _strategies_cache
    try:
        import httpx
        from app.middleware.tracing import get_correlation_id
        headers = {}
        cid = get_correlation_id()
        if cid:
            headers["X-Request-ID"] = cid
        resp = httpx.get(
            f"{core_api_url}/api/v1/ai-strategies/internal",
            timeout=5.0,
            headers=headers,
        )
        if resp.status_code == 200:
            _strategies_cache = resp.json()
            logger.info("ai_strategies_loaded", count=len(_strategies_cache))
            return _strategies_cache
        logger.warning("ai_strategies_bad_status", status=resp.status_code)
    except Exception as e:
        logger.warning("ai_strategies_fetch_failed", error=str(e))
    _strategies_cache = []
    return []


def build_strategies_prompt(core_api_url: str = "http://core-api:8001") -> str:
    """Сформировать блок бизнес-правил для system prompt LLM."""
    strategies = fetch_ai_strategies(core_api_url)
    if not strategies:
        return ""
    lines = ["\n=== БИЗНЕС-ПРАВИЛА (AI-стратегии) ==="]
    for s in strategies:
        lines.append(f"[Приоритет {s.get('priority', 0)}] {s.get('name', '')}: {s.get('rule_text', '')}")
    text = "\n".join(lines)
    return text[:3000]


def build_graph_rules_prompt(core_api_url: str = "http://core-api:8001") -> str:
    """Сформировать компактный текст правил для вставки в LLM system_prompt.

    Включает: номер графы, название, источники, ключевое AI-правило.
    Ограничение: не более 4000 символов, чтобы не перегружать контекст.
    """
    rules = fetch_db_rules(core_api_url)
    if not rules:
        return ""

    lines = [
        "=== ПРАВИЛА ЗАПОЛНЕНИЯ ГРАФ ДТ (краткий справочник) ===",
        "Используй при извлечении данных из документов:\n",
    ]
    for rule in rules:
        if rule.get("skip"):
            continue
        gn = rule.get("graph_number", "?")
        name = rule.get("graph_name", "")
        ai_rule = (rule.get("ai_rule") or "").strip()
        sources = rule.get("source_priority") or []

        if not ai_rule:
            continue

        src_str = f"[{', '.join(sources)}] " if sources else ""
        # Обрезаем длинные правила до 180 символов
        rule_short = ai_rule[:180] + ("…" if len(ai_rule) > 180 else "")
        lines.append(f"Гр.{gn} «{name}»: {src_str}{rule_short}")

    text = "\n".join(lines)
    # Жёсткое ограничение чтобы не перегружать контекст модели
    return text[:4000]


def get_source_priority_map(core_api_url: str = "http://core-api:8001") -> dict[int, list[str]]:
    """Вернуть словарь {graph_number: [source1, source2, ...]} из БД правил."""
    rules = fetch_db_rules(core_api_url)
    return {
        r["graph_number"]: r.get("source_priority") or []
        for r in rules
        if r.get("source_priority")
    }


def build_full_rules_for_llm(
    section: str = "header",
    core_api_url: str = "http://core-api:8001",
) -> str:
    """Сформировать ПОЛНЫЙ текст правил для LLM-компиляции декларации.

    В отличие от build_graph_rules_prompt(), не обрезает ai_rule и fill_instruction.
    Используется в _compile_by_rules() — отдельном LLM-шаге финального заполнения.
    section: 'header' — поля всей декларации, 'item' — поля товарной позиции.
    """
    rules = fetch_db_rules(core_api_url)
    if not rules:
        return ""

    lines = []
    for r in rules:
        if r.get("skip"):
            continue
        if r.get("section") != section:
            continue

        gn = r.get("graph_number", "?")
        name = r.get("graph_name", "")
        sources = r.get("source_priority") or []
        fill_inst = (r.get("fill_instruction") or "").strip()
        ai_rule = (r.get("ai_rule") or "").strip()
        target = r.get("target_field") or ""

        block = [f"--- ГРАФ {gn}: «{name}»"]
        if target:
            block.append(f"  Поле в декларации: {target}")
        if sources:
            block.append(f"  Источники (по приоритету): {', '.join(sources)}")
        if fill_inst:
            block.append(f"  Официальное правило: {fill_inst}")
        if ai_rule:
            block.append(f"  Инструкция для AI: {ai_rule}")
        lines.append("\n".join(block))

    return "\n\n".join(lines)
_VALID_COUNTRY = re.compile(r"^[A-Z]{2}$")
_VALID_HS10 = re.compile(r"^\d{10}$")
_VALID_CURRENCY = re.compile(r"^[A-Z]{3}$")
_INCOTERMS = {"EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP", "FAS", "FOB", "CFR", "CIF", "DAT"}


def _load_rules() -> dict:
    global _rules
    if _rules is not None:
        return _rules
    yaml_path = Path(__file__).parent.parent / "rules" / "declaration_mapping_v3.yaml"
    if not yaml_path.exists():
        logger.warning("rules_yaml_not_found", path=str(yaml_path))
        _rules = {}
        return _rules
    try:
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            _rules = yaml.safe_load(f) or {}
        logger.info("rules_loaded", graphs_header=len(_rules.get("header_graphs", [])),
                     graphs_items=len(_rules.get("item_graphs", [])),
                     checks=len(_rules.get("quality_checks", [])))
    except Exception as e:
        logger.warning("rules_yaml_parse_failed", error=str(e))
        _rules = {}
    return _rules


_filling_rules_text: str | None = None

_FILLING_RULES_PATHS = [
    Path("/app/docs/declaration_ai_filling_rules.md"),
    Path(__file__).resolve().parent.parent.parent.parent / "docs" / "declaration_ai_filling_rules.md",
]


def get_filling_rules_text() -> str:
    """Load and cache the human-readable filling rules (MD) for LLM prompts."""
    global _filling_rules_text
    if _filling_rules_text is not None:
        return _filling_rules_text

    for p in _FILLING_RULES_PATHS:
        if p.exists():
            try:
                _filling_rules_text = p.read_text(encoding="utf-8")
                logger.info("filling_rules_loaded", path=str(p), chars=len(_filling_rules_text))
                return _filling_rules_text
            except Exception as e:
                logger.warning("filling_rules_read_failed", path=str(p), error=str(e))

    logger.warning("filling_rules_not_found", searched=[str(p) for p in _FILLING_RULES_PATHS])
    _filling_rules_text = ""
    return _filling_rules_text


# ──────────────────────────────────────────────────────────────
# Evidence tracking helpers
# ──────────────────────────────────────────────────────────────

class EvidenceTracker:
    """Accumulates per-field evidence during _compile_declaration.

    Each entry stores the source document type, confidence score,
    and optionally a document_id that links to the specific
    Document record in core.documents after apply-parsed.
    """

    def __init__(self):
        self._map: dict[str, dict] = {}

    def record(self, field: str, value: Any, source: str, confidence: float = 0.7,
               graph: int | None = None, note: str = "",
               document_id: str | None = None):
        if value is None:
            return
        entry: dict = {
            "value_preview": str(value)[:120],
            "source": source,
            "confidence": round(confidence, 2),
            "graph": graph,
            "note": note,
        }
        if document_id:
            entry["document_id"] = document_id
        self._map[field] = entry

    def to_dict(self) -> dict:
        return dict(self._map)


# ──────────────────────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────────────────────

def _fmt(val: Any) -> str:
    return str(val)[:80] if val else "<пусто>"


def validate_declaration(result: dict, evidence_map: dict | None = None) -> list[dict]:
    """Run quality checks from YAML + hard-coded cross-checks.

    Returns a list of issue dicts:
        {"id": ..., "severity": "error"|"warning"|"info",
         "graph": <int or null>, "field": ..., "message": ...}
    """
    rules = _load_rules()
    issues: list[dict] = []

    def _issue(issue_id: str, severity: str, message: str,
               graph: int | None = None, field: str = ""):
        issues.append({
            "id": issue_id,
            "severity": severity,
            "graph": graph,
            "field": field,
            "message": message,
        })

    # ── Required header fields ───────────────────────────────
    _REQUIRED = [
        (1,  "type_code",              "Тип декларации"),
        (2,  "seller",                 "Отправитель"),
        (8,  "buyer",                  "Получатель"),
        (15, "country_origin",         "Страна отправления / происхождения"),
        (17, "country_destination",    "Страна назначения"),
        (22, "currency",               "Валюта"),
        (22, "total_amount",           "Сумма инвойса"),
        (25, "transport_type",         "Вид транспорта"),
    ]
    for graph_no, field, label in _REQUIRED:
        val = result.get(field)
        if val is None or val == "" or val == {}:
            _issue("missing_required", "error",
                   f"Графа {graph_no}: «{label}» не заполнена — нужен документ-источник",
                   graph=graph_no, field=field)

    # ── Format checks ────────────────────────────────────────
    cur = result.get("currency")
    if cur and not _VALID_CURRENCY.match(str(cur)):
        _issue("bad_currency", "error", f"Графа 22: валюта «{cur}» не в формате ISO 4217",
               graph=22, field="currency")

    for code_field, graph_no, label in [
        ("country_origin", 15, "Страна отправления"),
        ("country_destination", 17, "Страна назначения"),
    ]:
        v = result.get(code_field)
        if v and not _VALID_COUNTRY.match(str(v)):
            _issue("bad_country_code", "error",
                   f"Графа {graph_no}: «{label}» = «{v}» не ISO 3166 (2 буквы)",
                   graph=graph_no, field=code_field)

    inco = result.get("incoterms")
    if inco and str(inco).upper() not in _INCOTERMS:
        _issue("bad_incoterms", "warning",
               f"Графа 20: Incoterms «{inco}» — нестандартный код",
               graph=20, field="incoterms")

    tt = result.get("transport_type")
    if tt and str(tt) not in ("10", "20", "30", "40"):
        _issue("bad_transport_type", "warning",
               f"Графа 25: код транспорта «{tt}» — ожидается 10/20/30/40",
               graph=25, field="transport_type")

    # ── Items checks ─────────────────────────────────────────
    items = result.get("items", [])
    if not items:
        _issue("no_items", "error", "Нет товарных позиций — загрузите инвойс/спецификацию",
               field="items")

    for idx, item in enumerate(items):
        item_no = item.get("line_no", idx + 1)
        prefix = f"Позиция #{item_no}"

        desc = item.get("description") or item.get("commercial_name") or ""
        if not desc or len(desc.strip()) < 3 or re.match(r"^(item|товар|product|goods?|позиция|pos|position|line)\s*\d*$", desc.strip(), re.I):
            _issue("bad_item_description", "error",
                   f"{prefix}, графа 31: описание товара отсутствует или шаблонное",
                   graph=31, field=f"items[{idx}].description")

        hs = item.get("hs_code", "")
        if not hs:
            _issue("missing_hs_code", "error",
                   f"{prefix}, графа 33: код ТН ВЭД не указан",
                   graph=33, field=f"items[{idx}].hs_code")
        elif not _VALID_HS10.match(str(hs)):
            _issue("bad_hs_format", "error",
                   f"{prefix}, графа 33: код «{hs}» — нужно ровно 10 цифр",
                   graph=33, field=f"items[{idx}].hs_code")

        if item.get("hs_needs_review"):
            _issue("hs_needs_review", "warning",
                   f"{prefix}, графа 33: AI не уверен в коде ТН ВЭД — требуется проверка",
                   graph=33, field=f"items[{idx}].hs_code")

        gw = item.get("gross_weight")
        nw = item.get("net_weight")
        if gw is not None and nw is not None:
            try:
                if float(nw) > float(gw):
                    _issue("net_gt_gross", "warning",
                           f"{prefix}: нетто ({nw}) > брутто ({gw}) — проверьте",
                           graph=35, field=f"items[{idx}].gross_weight")
            except (ValueError, TypeError):
                pass

        if not item.get("unit_price"):
            _issue("missing_unit_price", "warning",
                   f"{prefix}, графа 42: цена за единицу не указана",
                   graph=42, field=f"items[{idx}].unit_price")

    # ── Cross-field checks (from quality_checks in YAML) ─────

    # weights_consistency
    if items:
        item_gross_sum = sum(float(it.get("gross_weight") or 0) for it in items)
        item_net_sum = sum(float(it.get("net_weight") or 0) for it in items)
        header_gross = result.get("total_gross_weight")
        header_net = result.get("total_net_weight")
        if header_gross and item_gross_sum > 0:
            try:
                diff_pct = abs(float(header_gross) - item_gross_sum) / max(float(header_gross), 0.01)
                if diff_pct > 0.05:
                    _issue("weights_mismatch", "warning",
                           f"Сумма брутто позиций ({item_gross_sum:.1f}) отличается от итога ({header_gross}) на {diff_pct:.0%}",
                           graph=35, field="total_gross_weight")
            except (ValueError, TypeError):
                pass

    # graph22_vs_graph42: sum(items[].line_total) vs total_amount
    if items:
        try:
            items_sum = sum(float(it.get("line_total") or 0) for it in items)
            header_total = result.get("total_amount")
            if header_total is not None and items_sum > 0:
                header_val = float(header_total)
                diff = abs(header_val - items_sum)
                threshold = max(header_val, items_sum) * 0.01
                if diff > threshold:
                    _issue("graph22_vs_graph42_mismatch", "warning",
                           f"Графа 22: сумма позиций (∑ гр.42) = {items_sum:.2f} "
                           f"≠ итогу инвойса = {header_val:.2f}, "
                           f"расхождение {diff:.2f}. Проверьте позиции и итог.",
                           graph=22, field="total_amount")
        except (ValueError, TypeError):
            pass

    # forms_count hint
    if items and not result.get("forms_count"):
        expected = math.ceil(len(items) / 3)
        _issue("forms_count_hint", "info",
               f"Графа 3: рекомендуемое кол-во форм = {expected} (по {len(items)} позициям)",
               graph=3, field="forms_count")

    # origin without certificate → cap confidence
    ev = evidence_map or {}
    origin_ev = ev.get("country_origin", {})
    if origin_ev and origin_ev.get("source") not in ("origin_certificate", "manufacturer_declaration"):
        _issue("origin_no_cert", "warning",
               f"Графа 16: страна происхождения «{result.get('country_origin')}» "
               f"определена из «{origin_ev.get('source', '?')}», а не из сертификата — confidence снижен",
               graph=16, field="country_origin")

    logger.info("rules_validation_done",
                errors=sum(1 for i in issues if i["severity"] == "error"),
                warnings=sum(1 for i in issues if i["severity"] == "warning"),
                infos=sum(1 for i in issues if i["severity"] == "info"))
    return issues
