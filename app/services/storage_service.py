from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.storage.factory import get_storage_provider
from app.models.domain import MediaAsset


class StorageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.provider = get_storage_provider()
        self.allowed_mimes = {m.strip() for m in self.settings.storage_allowed_mime.split(",") if m.strip()}

    async def sign_upload(
        self,
        owner_id: UUID,
        file_name: str,
        mime_type: str,
        size_bytes: int,
        checksum: str | None,
        test_id: int | None = None,
    ) -> tuple[MediaAsset, dict]:
        if mime_type not in self.allowed_mimes:
            raise HTTPException(status_code=400, detail="mime_type is not allowed")
        if size_bytes > self.settings.storage_max_file_size:
            raise HTTPException(status_code=400, detail="file too large")

        ext = Path(file_name).suffix.lower()
        object_key = f"uploads/{owner_id}/{uuid4().hex}{ext}"
        signed = self.provider.sign_upload(object_key=object_key, mime_type=mime_type, size_bytes=size_bytes)
        row = MediaAsset(
            owner_id=owner_id,
            test_id=test_id,
            provider=self.settings.storage_provider,
            bucket=signed.bucket,
            object_key=signed.object_key,
            public_url=signed.public_url,
            mime_type=mime_type,
            size_bytes=size_bytes,
            checksum=checksum,
            is_completed=False,
        )
        self.db.add(row)
        await self.db.flush()
        return row, {
            "upload_url": signed.upload_url,
            "method": signed.method,
            "headers": signed.headers,
            "asset_id": row.id,
            "public_url": row.public_url,
        }

    async def complete_upload(self, owner_id: UUID, asset_id: UUID) -> MediaAsset:
        res = await self.db.execute(select(MediaAsset).where(MediaAsset.id == asset_id))
        row = res.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset not found")
        if row.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        row.is_completed = True
        await self.db.flush()
        return row

