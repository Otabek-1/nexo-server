from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Plan, RefreshToken, Subscription, User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> User | None:
        res = await self.db.execute(select(User).where(User.email == email))
        return res.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        res = await self.db.execute(select(User).where(User.id == user_id))
        return res.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.db.add(user)
        await self.db.flush()
        return user

    async def store_refresh(self, user_id: UUID, token: str, expires_at: datetime) -> RefreshToken:
        row = RefreshToken(user_id=user_id, token=token, expires_at=expires_at)
        self.db.add(row)
        await self.db.flush()
        return row

    async def revoke_refresh(self, token: str) -> None:
        res = await self.db.execute(select(RefreshToken).where(RefreshToken.token == token))
        current = res.scalar_one_or_none()
        if current:
            current.revoked = True

    async def is_refresh_active(self, token: str) -> bool:
        res = await self.db.execute(select(RefreshToken).where(RefreshToken.token == token))
        current = res.scalar_one_or_none()
        if not current:
            return False
        if current.revoked:
            return False
        return current.expires_at > datetime.now(UTC)

    async def current_plan(self, user_id: UUID) -> Plan | None:
        res = await self.db.execute(
            select(Plan)
            .join(Subscription, Subscription.plan_id == Plan.id)
            .where(Subscription.user_id == user_id, Subscription.status == "active")
            .order_by(Subscription.started_at.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()

