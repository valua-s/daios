from __future__ import annotations

import logging

from minio import Minio

from backend.core.config import settings

logger = logging.getLogger(__name__)

minio_client = Minio(
    endpoint=settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=settings.minio_secure,
    region="us-east-1",
)


def ensure_bucket(bucket: str = settings.minio_bucket_media) -> None:
    """Создать бакет если не существует. Вызывается при старте приложения."""
    if not minio_client.bucket_exists(bucket):
        minio_client.make_bucket(bucket)
        logger.info("Created Minio bucket: %s", bucket)
