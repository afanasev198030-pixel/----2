from typing import Optional
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()


class RiskItem(BaseModel):
    rule_code: str
    severity: str  # low, medium, high, critical
    message: str
    recommendation: str


class RiskAssessment(BaseModel):
    overall_risk_score: int  # 0-100
    overall_severity: str
    risks: list[RiskItem]


def assess(
    items: list[dict],
    total_customs_value: Optional[float] = None
) -> RiskAssessment:
    """
    Assess risk for declaration items based on various rules.
    """
    risks = []
    risk_score = 0
    
    if not items:
        return RiskAssessment(
            overall_risk_score=0,
            overall_severity="low",
            risks=[]
        )
    
    # Rule 1: WEIGHT_RATIO - check gross/net weight ratio
    for item in items:
        gross_weight = item.get("gross_weight")
        net_weight = item.get("net_weight")
        
        if gross_weight and net_weight and net_weight > 0:
            ratio = gross_weight / net_weight
            if ratio > 1.5:
                risks.append(RiskItem(
                    rule_code="WEIGHT_RATIO",
                    severity="high",
                    message=f"Подозрительное соотношение веса брутто/нетто: {ratio:.2f}",
                    recommendation="Проверьте правильность указания весов. Соотношение превышает 1.5."
                ))
                risk_score += 20
    
    # Rule 2: PRICE_ANOMALY - suspiciously low unit price
    for item in items:
        unit_price = item.get("unit_price")
        if unit_price is not None and unit_price < 0.5:
            risks.append(RiskItem(
                rule_code="PRICE_ANOMALY",
                severity="medium",
                message=f"Подозрительно низкая цена за единицу: {unit_price:.2f}",
                recommendation="Проверьте корректность указания цены. Цена кажется заниженной."
            ))
            risk_score += 15
    
    # Rule 3: HIGH_RISK_HS - restricted goods codes
    high_risk_hs_prefixes = ["2402", "2208", "9303"]
    for item in items:
        hs_code = item.get("hs_code", "")
        if hs_code:
            for prefix in high_risk_hs_prefixes:
                if hs_code.startswith(prefix):
                    hs_name = {
                        "2402": "табачные изделия",
                        "2208": "алкогольная продукция",
                        "9303": "оружие и боеприпасы"
                    }.get(prefix, "ограниченные товары")
                    
                    risks.append(RiskItem(
                        rule_code="HIGH_RISK_HS",
                        severity="high",
                        message=f"Товар с кодом ТН ВЭД {hs_code} относится к категории: {hs_name}",
                        recommendation="Требуется дополнительная проверка и наличие специальных разрешений."
                    ))
                    risk_score += 25
                    break
    
    # Rule 4: MISSING_HS - missing HS code
    for idx, item in enumerate(items, 1):
        hs_code = item.get("hs_code")
        if not hs_code or hs_code.strip() == "":
            risks.append(RiskItem(
                rule_code="MISSING_HS",
                severity="critical",
                message=f"Позиция {idx}: отсутствует код ТН ВЭД",
                recommendation="Необходимо указать код ТН ВЭД для всех позиций товара."
            ))
            risk_score += 30
    
    # Rule 5: LOW_VALUE_HIGH_WEIGHT - suspicious value/weight ratio
    if total_customs_value is not None and total_customs_value < 1000:
        for item in items:
            gross_weight = item.get("gross_weight")
            if gross_weight and gross_weight > 100:
                risks.append(RiskItem(
                    rule_code="LOW_VALUE_HIGH_WEIGHT",
                    severity="medium",
                    message=f"Низкая стоимость декларации ({total_customs_value:.2f}) при большом весе товара ({gross_weight:.2f} кг)",
                    recommendation="Проверьте корректность указания таможенной стоимости."
                ))
                risk_score += 15
                break
    
    # Cap risk score at 100
    risk_score = min(100, risk_score)
    
    # Determine overall severity
    if risk_score <= 25:
        overall_severity = "low"
    elif risk_score <= 50:
        overall_severity = "medium"
    elif risk_score <= 75:
        overall_severity = "high"
    else:
        overall_severity = "critical"
    
    return RiskAssessment(
        overall_risk_score=risk_score,
        overall_severity=overall_severity,
        risks=risks
    )
