from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.domain import Submission


class SubmissionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, row: Submission) -> Submission:
        self.db.add(row)
        await self.db.flush()
        return row

    async def get(self, submission_id: UUID) -> Submission | None:
        res = await self.db.execute(
            select(Submission)
            .where(Submission.id == submission_id)
            .options(selectinload(Submission.manual_grades))
        )
        return res.scalar_one_or_none()

    async def list_for_test(self, test_id: int) -> list[Submission]:
        res = await self.db.execute(
            select(Submission)
            .where(Submission.test_id == test_id)
            .options(selectinload(Submission.manual_grades))
            .order_by(Submission.submitted_at.desc())
        )
        return list(res.scalars().all())
