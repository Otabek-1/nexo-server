from pathlib import Path
from urllib.parse import quote

from app.core.config import get_settings
from app.integrations.storage.base import SignedUpload, StorageProvider


class LocalStorageProvider(StorageProvider):
    name = "local"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_dir = Path(self.settings.storage_local_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.bucket = "local"

    def sign_upload(self, object_key: str, mime_type: str, size_bytes: int) -> SignedUpload:
        encoded_key = quote(object_key, safe="")
        return SignedUpload(
            upload_url=f"/api/v1/storage/local-upload/{encoded_key}",
            method="PUT",
            headers={"Content-Type": mime_type},
            public_url=f"/api/v1/storage/public/{encoded_key}",
            object_key=object_key,
            bucket=self.bucket,
        )

