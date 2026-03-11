from minio import Minio
from minio.error import S3Error
import structlog

from app.config import settings

logger = structlog.get_logger()

# Initialize MinIO client
minio_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE,
)


def ensure_bucket():
    """Create bucket if it doesn't exist."""
    try:
        if not minio_client.bucket_exists(settings.MINIO_BUCKET):
            minio_client.make_bucket(settings.MINIO_BUCKET)
            logger.info("bucket_created", bucket=settings.MINIO_BUCKET)
        else:
            logger.debug("bucket_exists", bucket=settings.MINIO_BUCKET)
    except S3Error as e:
        logger.error("bucket_creation_failed", bucket=settings.MINIO_BUCKET, error=str(e))
        raise


def upload_file(file_data: bytes, file_key: str, content_type: str) -> str:
    """
    Upload file to MinIO bucket.
    
    Args:
        file_data: File content as bytes
        file_key: S3-style key/path for the file
        content_type: MIME type of the file
        
    Returns:
        file_key: The key used to store the file
    """
    try:
        from io import BytesIO
        
        file_stream = BytesIO(file_data)
        file_size = len(file_data)
        
        minio_client.put_object(
            settings.MINIO_BUCKET,
            file_key,
            file_stream,
            file_size,
            content_type=content_type,
        )
        
        logger.info(
            "file_uploaded",
            file_key=file_key,
            file_size=file_size,
            content_type=content_type,
        )
        
        return file_key
    except S3Error as e:
        logger.error("file_upload_failed", file_key=file_key, error=str(e))
        raise


def download_file(file_key: str) -> bytes:
    """
    Download file from MinIO bucket.
    
    Args:
        file_key: S3-style key/path for the file
        
    Returns:
        File content as bytes
    """
    try:
        response = minio_client.get_object(settings.MINIO_BUCKET, file_key)
        file_data = response.read()
        response.close()
        response.release_conn()
        
        logger.info("file_downloaded", file_key=file_key, file_size=len(file_data))
        
        return file_data
    except S3Error as e:
        logger.error("file_download_failed", file_key=file_key, error=str(e))
        raise


def delete_file(file_key: str):
    """
    Delete file from MinIO bucket.
    
    Args:
        file_key: S3-style key/path for the file
    """
    try:
        minio_client.remove_object(settings.MINIO_BUCKET, file_key)
        logger.info("file_deleted", file_key=file_key)
    except S3Error as e:
        logger.error("file_delete_failed", file_key=file_key, error=str(e))
        raise


def file_exists(file_key: str) -> bool:
    """Check if file exists in MinIO without downloading it."""
    try:
        minio_client.stat_object(settings.MINIO_BUCKET, file_key)
        return True
    except S3Error:
        return False


def get_presigned_url(file_key: str, expires: int = 3600) -> str:
    """
    Get presigned URL for file download.
    
    Args:
        file_key: S3-style key/path for the file
        expires: Expiration time in seconds (default 3600)
        
    Returns:
        Presigned URL string
    """
    try:
        url = minio_client.presigned_get_object(
            settings.MINIO_BUCKET,
            file_key,
            expires=expires,
        )
        logger.debug("presigned_url_generated", file_key=file_key, expires=expires)
        return url
    except S3Error as e:
        logger.error("presigned_url_failed", file_key=file_key, error=str(e))
        raise
