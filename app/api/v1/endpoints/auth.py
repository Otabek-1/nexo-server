from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.core.ratelimit import rate_limit
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
)
from app.schemas.common import APIMessage
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
async def register(payload: RegisterRequest, request: Request, db: AsyncSession = Depends(db_session)):
    rate_limit(key=f"register:{request.client.host}", limit=20, window_seconds=60)
    service = AuthService(db)
    return await service.register(email=payload.email, full_name=payload.full_name, password=payload.password)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(db_session)):
    rate_limit(key=f"login:{request.client.host}", limit=30, window_seconds=60)
    service = AuthService(db)
    return await service.login(email=payload.email, password=payload.password)


@router.post("/refresh")
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(db_session)):
    service = AuthService(db)
    return await service.refresh(payload.refresh_token)


@router.post("/logout", response_model=APIMessage)
async def logout(payload: LogoutRequest, db: AsyncSession = Depends(db_session)):
    service = AuthService(db)
    await service.logout(payload.refresh_token)
    return APIMessage(message="Logged out")

