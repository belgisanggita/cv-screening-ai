from datetime import timedelta
from functools import lru_cache
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from app.config import settings
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


@lru_cache
def get_minio_client() -> Minio:
    logger.info(f"Connecting to MinIO at {settings.MINIO_ENDPOINT}")
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


def ensure_bucket() -> None:
    client = get_minio_client()
    bucket = settings.MINIO_BUCKET

    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info(f"Created bucket '{bucket}'")
    else:
        logger.info(f"Bucket '{bucket}' already exists")


def upload_cv(file_bytes: bytes, object_name: str, content_type: str = "application/pdf") -> str:
    client = get_minio_client()
    bucket = settings.MINIO_BUCKET

    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=BytesIO(file_bytes),
        length=len(file_bytes),
        content_type=content_type,
    )
    logger.info(f"Uploaded '{object_name}' to bucket '{bucket}'")
    return f"{bucket}/{object_name}"


def get_presigned_url(object_name: str, bucket_name: str | None = None, expires_minutes: int = 60) -> str | None:
    client = get_minio_client()
    bucket = bucket_name or settings.MINIO_BUCKET

    try:
        return client.presigned_get_object(
            bucket_name=bucket,
            object_name=object_name,
            expires=timedelta(minutes=expires_minutes),
        )
    except S3Error as e:
        logger.error(f"Failed to generate presigned URL for '{object_name}': {e}")
        return None

def stat_object(object_name: str) -> bool:
    """Cek apakah object ada di bucket, tanpa fetch isinya."""
    client = get_minio_client()
    bucket = settings.MINIO_BUCKET

    try:
        client.stat_object(bucket, object_name)
        return True
    except S3Error as e:
        logger.warning(f"Object '{object_name}' not found in bucket '{bucket}': {e}")
        return False


def get_object_bytes(object_name: str) -> bytes:
    """Fetch isi file dari MinIO sebagai bytes."""
    client = get_minio_client()
    bucket = settings.MINIO_BUCKET

    response = None
    try:
        response = client.get_object(bucket, object_name)
        return response.read()
    except S3Error as e:
        logger.error(f"Failed to fetch object '{object_name}' from bucket '{bucket}': {e}")
        raise
    finally:
        if response:
            response.close()
            response.release_conn()