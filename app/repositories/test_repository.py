from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import SubmissionStatus
from app.models.domain import Question, Submission, Test


class TestRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_creator_tests(self, creator_id: UUID) -> list[Test]:
        res = await self.db.execute(
            select(Test)
            .where(Test.creator_id == creator_id)
            .options(selectinload(Test.questions))
            .order_by(Test.created_at.desc())
        )
        return list(res.scalars().all())

    async def get_by_id(self, test_id: int) -> Test | None:
        res = await self.db.execute(
            select(Test)
            .where(Test.id == test_id)
            .options(
                selectinload(Test.questions).selectinload(Question.options),
                selectinload(Test.participant_fields),
            )
        )
        return res.scalar_one_or_none()

    async def add(self, row: Test) -> Test:
        self.db.add(row)
        await self.db.flush()
        return row

    async def delete(self, row: Test) -> None:
        await self.db.delete(row)

    async def stats(self, test_id: int) -> tuple[int, int]:
        total_res = await self.db.execute(
            select(func.count(Submission.id)).where(Submission.test_id == test_id)
        )
        pending_res = await self.db.execute(
            select(func.count(Submission.id)).where(
                Submission.test_id == test_id,
                Submission.status == SubmissionStatus.PENDING_REVIEW,
            )
        )
        return int(total_res.scalar() or 0), int(pending_res.scalar() or 0)
