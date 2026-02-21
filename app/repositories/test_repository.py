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
            .options(
                selectinload(Test.participant_fields),
            )
            .order_by(Test.created_at.desc())
        )
        return list(res.scalars().all())

    async def count_creator_tests(self, creator_id: UUID) -> int:
        res = await self.db.execute(select(func.count(Test.id)).where(Test.creator_id == creator_id))
        return int(res.scalar() or 0)

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

    async def question_counts_bulk(self, test_ids: list[int]) -> dict[int, int]:
        if not test_ids:
            return {}
        res = await self.db.execute(
            select(Question.test_id, func.count(Question.id))
            .where(Question.test_id.in_(test_ids))
            .group_by(Question.test_id)
        )
        return {int(test_id): int(count) for test_id, count in res.all()}

    async def submission_stats_bulk(self, test_ids: list[int]) -> dict[int, tuple[int, int]]:
        if not test_ids:
            return {}

        total_res = await self.db.execute(
            select(Submission.test_id, func.count(Submission.id))
            .where(Submission.test_id.in_(test_ids))
            .group_by(Submission.test_id)
        )
        pending_res = await self.db.execute(
            select(Submission.test_id, func.count(Submission.id))
            .where(
                Submission.test_id.in_(test_ids),
                Submission.status == SubmissionStatus.PENDING_REVIEW,
            )
            .group_by(Submission.test_id)
        )

        totals = {int(test_id): int(count) for test_id, count in total_res.all()}
        pendings = {int(test_id): int(count) for test_id, count in pending_res.all()}
        return {
            test_id: (totals.get(test_id, 0), pendings.get(test_id, 0))
            for test_id in test_ids
        }
