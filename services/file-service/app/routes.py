from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse, Response
from io import BytesIO
import structlog
import httpx
from datetime import datetime
from uuid import uuid4
import re

from app.storage import upload_file, download_file, delete_file, get_presigned_url, file_exists
from app.config import settings

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/files", tags=["files"])

# Maximum file size: 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024

# Allowed MIME types
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/vnd.ms-excel",  # .xls
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/xml",
    "text/xml",
}


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    # Remove path components
    filename = filename.split("/")[-1].split("\\")[-1]
    # Replace unsafe characters
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:250] + ('.' + ext if ext else '')
    return filename


@router.post("/upload")
async def upload_file_endpoint(file: UploadFile = File(...)):
    """
    Upload a file to MinIO storage.
    
    Validates file size (max 50MB) and MIME type.
    Returns file_key, original_filename, mime_type, and file_size.
    """
    # Validate MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        logger.warning(
            "upload_rejected_invalid_mime",
            filename=file.filename,
            content_type=file.content_type,
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(sorted(ALLOWED_MIME_TYPES))}",
        )
    
    # Read file content
    file_data = await file.read()
    file_size = len(file_data)
    
    # Validate file size
    if file_size > MAX_FILE_SIZE:
        logger.warning(
            "upload_rejected_size_exceeded",
            filename=file.filename,
            file_size=file_size,
            max_size=MAX_FILE_SIZE,
        )
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / (1024 * 1024):.0f}MB",
        )
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    # Generate file_key: {year}/{month}/{uuid4}_{sanitized_filename}
    now = datetime.utcnow()
    sanitized_filename = sanitize_filename(file.filename or "unnamed")
    file_uuid = str(uuid4())
    file_key = f"{now.year}/{now.month:02d}/{file_uuid}_{sanitized_filename}"
    
    # Upload to MinIO
    try:
        upload_file(file_data, file_key, file.content_type)
        
        logger.info(
            "file_uploaded_success",
            file_key=file_key,
            original_filename=file.filename,
            file_size=file_size,
            mime_type=file.content_type,
        )
        
        return {
            "file_key": file_key,
            "original_filename": file.filename,
            "mime_type": file.content_type,
            "file_size": file_size,
        }
    except Exception as e:
        logger.error(
            "file_upload_error",
            filename=file.filename,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to upload file")


@router.head("/check/{file_key:path}")
@router.get("/check/{file_key:path}")
async def check_file_exists(file_key: str):
    """Check if file exists in storage. Returns 200 or 404."""
    if file_exists(file_key):
        return {"exists": True, "file_key": file_key}
    raise HTTPException(status_code=404, detail="File not found")


CONVERTIBLE_EXTENSIONS = {
    ".xlsx", ".xls", ".docx", ".doc", ".odt", ".ods", ".pptx", ".ppt", ".csv", ".rtf",
}


def _is_pdf(file_key: str) -> bool:
    return file_key.lower().endswith(".pdf")


def _is_image(file_key: str) -> bool:
    return any(file_key.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"))


def _is_convertible(file_key: str) -> bool:
    return any(file_key.lower().endswith(ext) for ext in CONVERTIBLE_EXTENSIONS)


def _cache_key(file_key: str) -> str:
    return f"{file_key}.pdf"


async def _convert_to_pdf(file_data: bytes, filename: str) -> bytes:
    async with httpx.AsyncClient() as client:
        files = {"files": (filename, file_data)}
        response = await client.post(
            f"{settings.GOTENBERG_URL}/forms/libreoffice/convert",
            files=files,
            timeout=120.0,
        )
        response.raise_for_status()
        return response.content


@router.get("/pdf-preview/{file_key:path}")
async def pdf_preview(file_key: str):
    """
    Return PDF version of a document. For PDFs — returns as-is.
    For Office documents — converts via Gotenberg and caches.
    For images — returns 400 (use direct download instead).
    """
    if _is_image(file_key):
        raise HTTPException(status_code=400, detail="Images should be viewed directly, not converted to PDF")

    if _is_pdf(file_key):
        try:
            file_data = download_file(file_key)
            return Response(content=file_data, media_type="application/pdf")
        except Exception as e:
            logger.error("pdf_preview_download_error", file_key=file_key, error=str(e))
            raise HTTPException(status_code=404, detail="File not found")

    if not _is_convertible(file_key):
        raise HTTPException(status_code=400, detail=f"Unsupported format for PDF preview")

    cached_key = _cache_key(file_key)
    if file_exists(cached_key):
        logger.info("pdf_preview_cache_hit", file_key=file_key, cached_key=cached_key)
        try:
            cached_data = download_file(cached_key)
            return Response(content=cached_data, media_type="application/pdf")
        except Exception:
            pass

    try:
        original_data = download_file(file_key)
    except Exception as e:
        logger.error("pdf_preview_original_not_found", file_key=file_key, error=str(e))
        raise HTTPException(status_code=404, detail="Original file not found")

    filename = file_key.split("/")[-1]
    try:
        pdf_bytes = await _convert_to_pdf(original_data, filename)
    except httpx.HTTPStatusError as e:
        logger.error("gotenberg_conversion_failed", file_key=file_key, status=e.response.status_code)
        raise HTTPException(status_code=502, detail="Document conversion failed")
    except Exception as e:
        logger.error("gotenberg_connection_error", file_key=file_key, error=str(e))
        raise HTTPException(status_code=502, detail="Conversion service unavailable")

    try:
        upload_file(pdf_bytes, cached_key, "application/pdf")
        logger.info("pdf_preview_cached", file_key=file_key, cached_key=cached_key, pdf_size=len(pdf_bytes))
    except Exception as e:
        logger.warning("pdf_preview_cache_write_failed", file_key=file_key, error=str(e))

    return Response(content=pdf_bytes, media_type="application/pdf")


@router.get("/download/{file_key:path}")
async def download_file_endpoint(file_key: str):
    """
    Download a file from MinIO storage.
    
    Returns a redirect to a presigned URL or streams the file directly.
    """
    try:
        # Option 1: Return presigned URL (redirect)
        presigned_url = get_presigned_url(file_key, expires=3600)
        logger.info("file_download_requested", file_key=file_key)
        return RedirectResponse(url=presigned_url, status_code=307)
        
        # Option 2: Stream file directly (uncomment if preferred)
        # file_data = download_file(file_key)
        # return StreamingResponse(
        #     BytesIO(file_data),
        #     media_type="application/octet-stream",
        #     headers={"Content-Disposition": f'attachment; filename="{file_key.split("/")[-1]}"'},
        # )
    except Exception as e:
        logger.error(
            "file_download_error",
            file_key=file_key,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(status_code=404, detail="File not found")


@router.delete("/{file_key:path}")
async def delete_file_endpoint(file_key: str):
    """
    Delete a file from MinIO storage.
    
    Returns 204 No Content on success.
    """
    try:
        delete_file(file_key)
        logger.info("file_deleted_success", file_key=file_key)
        return None  # FastAPI will return 204
    except Exception as e:
        logger.error(
            "file_delete_error",
            file_key=file_key,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(status_code=404, detail="File not found")
