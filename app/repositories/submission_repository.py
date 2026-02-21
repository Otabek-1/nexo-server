from uuid import UUID

from sqlalchemy import func, select
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

    async def list_for_test(self, test_id: int, include_manual_grades: bool = True) -> list[Submission]:
        query = select(Submission).where(Submission.test_id == test_id).order_by(Submission.submitted_at.desc())
        if include_manual_grades:
            query = query.options(selectinload(Submission.manual_grades))
        res = await self.db.execute(query)
        return list(res.scalars().all())

    async def count_for_attempt_value(self, test_id: int, participant_attempt_value: str) -> int:
        res = await self.db.execute(
            select(func.count(Submission.id)).where(
                Submission.test_id == test_id,
                Submission.participant_attempt_value == participant_attempt_value,
            )
        )
        return int(res.scalar() or 0)

    async def count_for_test(self, test_id: int) -> int:
        res = await self.db.execute(select(func.count(Submission.id)).where(Submission.test_id == test_id))
        return int(res.scalar() or 0)
