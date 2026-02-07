from fastapi import APIRouter, UploadFile, File, HTTPException
import structlog

from app.services import invoice_parser, packing_parser, contract_parser

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/ai/parse", tags=["parser"])


@router.post("/invoice")
async def parse_invoice(file: UploadFile = File(...)):
    """
    Parse invoice document (PDF/JPG) and extract structured data.
    """
    try:
        file_bytes = await file.read()
        result = invoice_parser.parse(file_bytes, file.filename or "invoice.pdf")
        return result
    except Exception as e:
        logger.error("invoice_parse_error", error=str(e), filename=file.filename)
        raise HTTPException(status_code=500, detail=f"Failed to parse invoice: {str(e)}")


@router.post("/packing-list")
async def parse_packing_list(file: UploadFile = File(...)):
    """
    Parse packing list document and extract structured data.
    """
    try:
        file_bytes = await file.read()
        result = packing_parser.parse(file_bytes, file.filename or "packing_list.pdf")
        return result
    except Exception as e:
        logger.error("packing_list_parse_error", error=str(e), filename=file.filename)
        raise HTTPException(status_code=500, detail=f"Failed to parse packing list: {str(e)}")


@router.post("/contract")
async def parse_contract(file: UploadFile = File(...)):
    """
    Parse contract document and extract structured data.
    """
    try:
        file_bytes = await file.read()
        result = contract_parser.parse(file_bytes, file.filename or "contract.pdf")
        return result
    except Exception as e:
        logger.error("contract_parse_error", error=str(e), filename=file.filename)
        raise HTTPException(status_code=500, detail=f"Failed to parse contract: {str(e)}")
