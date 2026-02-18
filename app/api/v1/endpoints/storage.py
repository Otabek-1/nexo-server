from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_current_user
from app.core.config import get_settings
from app.schemas.storage import (
    AssetOut,
    CompleteUploadRequest,
    SignUploadRequest,
    SignedUploadResponse,
)
from app.services.storage_service import StorageService

router = APIRouter(prefix="/storage", tags=["storage"])


@router.post("/uploads/sign", response_model=SignedUploadResponse)
async def sign_upload(
    payload: SignUploadRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
):
    service = StorageService(db)
    _, data = await service.sign_upload(
        owner_id=user.id,
        file_name=payload.file_name,
        mime_type=payload.mime_type,
        size_bytes=payload.size_bytes,
        checksum=payload.checksum,
        test_id=payload.test_id,
    )
    await db.commit()
    return SignedUploadResponse(**data)


@router.post("/uploads/complete", response_model=AssetOut)
async def complete_upload(
    payload: CompleteUploadRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
):
    service = StorageService(db)
    row = await service.complete_upload(owner_id=user.id, asset_id=payload.asset_id)
    await db.commit()
    return AssetOut(
        id=row.id,
        public_url=row.public_url,
        bucket=row.bucket,
        object_key=row.object_key,
        mime_type=row.mime_type,
        size_bytes=row.size_bytes,
        provider=row.provider,
    )


@router.put("/local-upload/{object_key:path}")
async def local_upload(object_key: str, request: Request):
    settings = get_settings()
    if settings.storage_provider != "local":
        raise HTTPException(status_code=404, detail="Not found")
    body = await request.body()
    base = Path(settings.storage_local_dir).resolve()
    target = (base / object_key).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Invalid path")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    return {"ok": True}


@router.get("/public/{object_key:path}")
async def local_public(object_key: str):
    settings = get_settings()
    if settings.storage_provider != "local":
        raise HTTPException(status_code=404, detail="Not found")
    base = Path(settings.storage_local_dir).resolve()
    target = (base / object_key).resolve()
    if not target.exists():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(target)

