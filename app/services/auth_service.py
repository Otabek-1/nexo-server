from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import Role
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models.domain import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthResponse, AuthTokens, UserOut


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserRepository(db)
        self.settings = get_settings()

    async def register(self, email: str, full_name: str, password: str) -> AuthResponse:
        normalized = email.strip().lower()
        existing = await self.repo.get_by_email(normalized)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

        user = User(
            email=normalized,
            full_name=full_name.strip(),
            password_hash=hash_password(password),
            role=Role.CREATOR,
        )
        await self.repo.create(user)
        tokens = await self._issue_tokens(user.id, user.email)
        await self.db.commit()
        return AuthResponse(user=UserOut.model_validate(user), tokens=tokens)

    async def login(self, email: str, password: str) -> AuthResponse:
        normalized = email.strip().lower()
        user = await self.repo.get_by_email(normalized)
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        tokens = await self._issue_tokens(user.id, user.email)
        await self.db.commit()
        return AuthResponse(user=UserOut.model_validate(user), tokens=tokens)

    async def refresh(self, refresh_token: str) -> AuthTokens:
        payload = decode_refresh_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        if not await self.repo.is_refresh_active(refresh_token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")
        user = await self.repo.get_by_id(payload["sub"])
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        await self.repo.revoke_refresh(refresh_token)
        tokens = await self._issue_tokens(user.id, user.email)
        await self.db.commit()
        return tokens

    async def logout(self, refresh_token: str) -> None:
        await self.repo.revoke_refresh(refresh_token)
        await self.db.commit()

    async def _issue_tokens(self, user_id, email: str) -> AuthTokens:
        access = create_access_token(user_id=user_id, email=email)
        refresh = create_refresh_token(user_id=user_id)
        expires = datetime.now(UTC) + timedelta(days=self.settings.jwt_refresh_ttl_days)
        await self.repo.store_refresh(user_id=user_id, token=refresh, expires_at=expires)
        return AuthTokens(
            access_token=access,
            refresh_token=refresh,
            token_type="bearer",
            expires_in=self.settings.jwt_access_ttl_min * 60,
        )

