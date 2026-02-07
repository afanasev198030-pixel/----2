from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import structlog

from app.services import risk_engine

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/ai", tags=["risk"])


class RiskItemRequest(BaseModel):
    hs_code: Optional[str] = None
    country_origin: Optional[str] = None
    unit_price: Optional[float] = None
    gross_weight: Optional[float] = None
    net_weight: Optional[float] = None


class AssessRiskRequest(BaseModel):
    items: list[RiskItemRequest]
    total_customs_value: Optional[float] = None


@router.post("/assess-risk")
async def assess_risk(request: AssessRiskRequest):
    """
    Assess risk for declaration items.
    """
    try:
        # Convert request items to dict format
        items_dict = [
            {
                "hs_code": item.hs_code,
                "country_origin": item.country_origin,
                "unit_price": item.unit_price,
                "gross_weight": item.gross_weight,
                "net_weight": item.net_weight,
            }
            for item in request.items
        ]
        
        result = risk_engine.assess(
            items=items_dict,
            total_customs_value=request.total_customs_value
        )
        return result
    except Exception as e:
        logger.error("risk_assess_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to assess risk: {str(e)}")
