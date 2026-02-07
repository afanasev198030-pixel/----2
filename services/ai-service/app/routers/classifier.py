from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import structlog

from app.services import hs_classifier

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/ai", tags=["classifier"])


class ClassifyRequest(BaseModel):
    description: str
    country_origin: Optional[str] = None
    unit_price: Optional[float] = None


@router.post("/classify-hs")
async def classify_hs(request: ClassifyRequest):
    """
    Classify goods description to HS code suggestions.
    """
    try:
        suggestions = hs_classifier.classify(
            description=request.description,
            country_origin=request.country_origin,
            unit_price=request.unit_price
        )
        return {"suggestions": suggestions}
    except Exception as e:
        logger.error("hs_classify_error", error=str(e), description=request.description)
        raise HTTPException(status_code=500, detail=f"Failed to classify HS code: {str(e)}")
