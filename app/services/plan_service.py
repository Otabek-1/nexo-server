from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DEFAULT_FREE_LIMITS, PlanCode
from app.models.domain import Plan, Subscription

PRO_LIMITS = {
    "activeTests": 999999,
    "questionsPerTest": 1000000,
    "submissionsPerTest": 1000000,
    "manualReviewRecent": 1000000,
}


class PlanService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ensure_seed_plans(self) -> None:
        existing = await self.db.execute(select(Plan))
        if existing.scalars().first():
            return
        self.db.add_all(
            [
                Plan(code=PlanCode.FREE, limits=DEFAULT_FREE_LIMITS),
                Plan(code=PlanCode.PRO, limits=PRO_LIMITS),
                Plan(code=PlanCode.LIFETIME, limits=PRO_LIMITS),
            ]
        )
        await self.db.commit()

    async def get_available(self) -> list[Plan]:
        result = await self.db.execute(select(Plan))
        return list(result.scalars().all())

    async def get_user_plan(self, user_id: UUID) -> PlanCode:
        result = await self.db.execute(
            select(Plan.code)
            .join(Subscription, Subscription.plan_id == Plan.id)
            .where(Subscription.user_id == user_id, Subscription.status == "active")
            .order_by(Subscription.started_at.desc())
            .limit(1)
        )
        code = result.scalar_one_or_none()
        return code or PlanCode.FREE

    async def set_user_plan(self, user_id: UUID, plan_code: PlanCode, billing_cycle: str) -> Subscription:
        active_rows = await self.db.execute(
            select(Subscription).where(Subscription.user_id == user_id, Subscription.status == "active")
        )
        for row in active_rows.scalars().all():
            row.status = "inactive"

        plan_res = await self.db.execute(select(Plan).where(Plan.code == plan_code))
        plan = plan_res.scalar_one()
        sub = Subscription(
            user_id=user_id,
            plan_id=plan.id,
            status="active",
            billing_cycle=billing_cycle,
            started_at=datetime.now(UTC),
        )
        self.db.add(sub)
        await self.db.flush()
        return sub

