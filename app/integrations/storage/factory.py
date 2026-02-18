from app.core.config import get_settings
from app.integrations.storage.base import StorageProvider
from app.integrations.storage.local import LocalStorageProvider
from app.integrations.storage.s3 import S3StorageProvider


def get_storage_provider() -> StorageProvider:
    settings = get_settings()
    if settings.storage_provider in {"minio", "supabase"}:
        return S3StorageProvider()
    return LocalStorageProvider()

