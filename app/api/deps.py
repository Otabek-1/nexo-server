from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import PlanCode
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.domain import User
from app.repositories.user_repository import UserRepository
from app.services.plan_service import PlanService

bearer = HTTPBearer(auto_error=False)


async def db_session() -> AsyncSession:
    async for s in get_db():
        yield s


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(db_session),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth token")
    try:
        payload = decode_access_token(credentials.credentials)
        if payload.get("type") != "access":
            raise ValueError("invalid token type")
        user_id = UUID(payload["sub"])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth token") from exc
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive")
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(db_session),
) -> User | None:
    if not credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        if payload.get("type") != "access":
            return None
        user_id = UUID(payload["sub"])
    except Exception:
        return None
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user or not user.is_active:
        return None
    return user


async def get_current_plan(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
) -> PlanCode:
    service = PlanService(db)
    return await service.get_user_plan(user.id)


def get_idempotency_key(request: Request) -> str | None:
    return request.headers.get("Idempotency-Key")
