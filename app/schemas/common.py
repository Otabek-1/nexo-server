from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class APIMessage(BaseModel):
    message: str


class Pagination(BaseModel):
    page: int = 1
    page_size: int = 20


class CurrentUser(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    plan: str


class AuditPayload(BaseModel):
    action: str
    entity_type: str
    entity_id: str
    payload: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

