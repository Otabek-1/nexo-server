from uuid import UUID

from pydantic import BaseModel, Field


class SignUploadRequest(BaseModel):
    file_name: str
    mime_type: str
    size_bytes: int = Field(gt=0)
    checksum: str | None = None
    test_id: int | None = None


class SignedUploadResponse(BaseModel):
    upload_url: str
    method: str
    headers: dict[str, str]
    asset_id: UUID
    public_url: str


class CompleteUploadRequest(BaseModel):
    asset_id: UUID


class AssetOut(BaseModel):
    id: UUID
    public_url: str
    bucket: str
    object_key: str
    mime_type: str
    size_bytes: int
    provider: str

