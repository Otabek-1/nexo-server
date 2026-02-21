from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    DEFAULT_FREE_LIMITS,
    PlanCode,
    QuestionType,
    ScoringType,
    SubmissionStatus,
)
from app.models.domain import ManualGrade, Submission, Test
from app.repositories.submission_repository import SubmissionRepository
from app.services.plan_service import PlanService
from app.services.rasch_service import estimate_rasch_1pl, theta_to_score_100
from app.services.scoring_service import auto_score_submission, is_question_correct
from app.services.test_service import TestService


class SubmissionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SubmissionRepository(db)
        self.test_service = TestService(db)
        self.plan_service = PlanService(db)

    async def create_submission(
        self,
        test_id: int,
        participant_values: dict[str, str],
        answers: dict[str, str | int | float],
        idempotency_key: str | None = None,
    ) -> dict:
        test = await self.test_service.get_test_or_404(test_id)
        now = datetime.now(UTC)
        if now < test.start_time or now >= test.end_time:
            raise HTTPException(status_code=400, detail="Test not active")

        attempt_value = str(participant_values.get("fullName") or "").strip()
        if not attempt_value:
            raise HTTPException(status_code=400, detail="fullName required")

        attempts_query = await self.db.execute(
            select(Submission).where(
                Submission.test_id == test_id, Submission.participant_attempt_value == attempt_value
            )
        )
        attempts = len(attempts_query.scalars().all())
        if attempts >= test.attempts_count:
            raise HTTPException(status_code=400, detail="Attempt limit reached")

        if idempotency_key:
            existing = await self.db.execute(
                select(Submission).where(
                    Submission.test_id == test_id, Submission.idempotency_key == idempotency_key
                )
            )
            current = existing.scalar_one_or_none()
            if current:
                return self.serialize_submission(current)

        if test.creator_plan_snapshot == PlanCode.FREE:
            count = await self.db.execute(select(Submission).where(Submission.test_id == test_id))
            if len(count.scalars().all()) >= DEFAULT_FREE_LIMITS["submissionsPerTest"]:
                raise HTTPException(status_code=400, detail="Free submissionsPerTest limit reached")

        auto_score, auto_max, status = auto_score_submission(
            test.questions, answers, test.scoring_type
        )
        final_score = auto_score if status == SubmissionStatus.COMPLETED else None
        secondary = str(participant_values.get("phone", "")).strip()

        row = Submission(
            test_id=test_id,
            participant_full_name=attempt_value,
            participant_attempt_value=attempt_value,
            participant_secondary=secondary,
            participant_fields_json=participant_values,
            answers_json={str(k): v for k, v in answers.items()},
            auto_score=auto_score,
            auto_max_score=auto_max,
            final_score=final_score,
            status=status,
            idempotency_key=idempotency_key,
        )
        await self.repo.create(row)
        await self.db.commit()
        await self.db.refresh(row)
        return self.serialize_submission(row)

    async def list_submissions(self, test_id: int, user_id: UUID, status: str | None, latest: int | None) -> list[dict]:
        test = await self.test_service.get_test_or_404(test_id)
        if test.creator_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        rows = await self.repo.list_for_test(test_id)
        if status:
            rows = [s for s in rows if s.status.value == status]
        if test.creator_plan_snapshot == PlanCode.FREE:
            rows = rows[: DEFAULT_FREE_LIMITS["manualReviewRecent"]]
        if latest:
            rows = rows[:latest]
        return [self.serialize_submission(s) for s in rows]

    async def patch_manual_grades(
        self, test_id: int, submission_id: UUID, user_id: UUID, grades: dict[str, float]
    ) -> dict:
        test = await self.test_service.get_test_or_404(test_id)
        if test.creator_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        submission = await self.repo.get(submission_id)
        if not submission or submission.test_id != test_id:
            raise HTTPException(status_code=404, detail="Submission not found")

        for qid, score in grades.items():
            q_uuid = UUID(str(qid))
            existing = next((g for g in submission.manual_grades if g.question_id == q_uuid), None)
            bounded = max(0.0, float(score))
            if existing:
                existing.score = bounded
                existing.grader_id = user_id
            else:
                submission.manual_grades.append(
                    ManualGrade(question_id=q_uuid, score=bounded, grader_id=user_id)
                )
        await self.db.commit()
        await self.db.refresh(submission)
        return self.serialize_submission(submission)

    async def finalize_submission(
        self, test_id: int, submission_id: UUID, user_id: UUID, override: float | None
    ) -> dict:
        test = await self.test_service.get_test_or_404(test_id)
        if test.creator_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        if test.creator_plan_snapshot == PlanCode.FREE:
            raise HTTPException(status_code=400, detail="Finalize requires pro")

        submission = await self.repo.get(submission_id)
        if not submission or submission.test_id != test_id:
            raise HTTPException(status_code=404, detail="Submission not found")

        if test.scoring_type == ScoringType.RASCH:
            await self._finalize_rasch_for_test(
                test=test,
                triggering_submission_id=submission_id,
                reviewer_id=user_id,
                override=override,
            )
            refreshed = await self.repo.get(submission_id)
            if not refreshed:
                raise HTTPException(status_code=404, detail="Submission not found")
            await self.db.commit()
            return self.serialize_submission(refreshed)

        manual_total, _, _ = self._manual_component(submission=submission, test=test)
        submission.final_score = submission.auto_score + manual_total
        submission.status = SubmissionStatus.COMPLETED
        submission.reviewed_at = datetime.now(UTC)
        submission.review_by = user_id
        await self.db.commit()
        await self.db.refresh(submission)
        return self.serialize_submission(submission)

    async def leaderboard(self, test_id: int) -> dict:
        rows = await self.repo.list_for_test(test_id)
        ranked = sorted(
            [s for s in rows if s.status == SubmissionStatus.COMPLETED and s.final_score is not None],
            key=lambda x: (-float(x.final_score or 0), x.submitted_at),
        )
        pending = sorted(
            [s for s in rows if s.status != SubmissionStatus.COMPLETED],
            key=lambda x: x.submitted_at,
            reverse=True,
        )
        return {
            "ranked": [
                {
                    "id": s.id,
                    "participant": self._participant(s),
                    "finalScore": float(s.final_score or 0),
                    "submittedAt": s.submitted_at,
                }
                for s in ranked
            ],
            "pending": [
                {
                    "id": s.id,
                    "participant": self._participant(s),
                    "submittedAt": s.submitted_at,
                    "status": s.status.value,
                }
                for s in pending
            ],
            "stats": {
                "ranked": len(ranked),
                "pending": len(pending),
                "total": len(rows),
            },
        }

    def serialize_submission(self, row: Submission) -> dict:
        state = inspect(row)
        if "manual_grades" in state.unloaded:
            manual = {}
        else:
            manual = {str(g.question_id): float(g.score) for g in row.manual_grades}
        return {
            "id": row.id,
            "testId": row.test_id,
            "participant": self._participant(row),
            "answers": row.answers_json,
            "autoScore": row.auto_score,
            "autoMaxScore": row.auto_max_score,
            "finalScore": row.final_score,
            "status": row.status.value,
            "submittedAt": row.submitted_at,
            "manualGrades": manual,
            "reviewedAt": row.reviewed_at,
        }

    def _participant(self, row: Submission) -> dict:
        return {
            "fullName": row.participant_full_name,
            "phone": row.participant_secondary,
            "fields": row.participant_fields_json,
            "attemptValue": row.participant_attempt_value,
        }

    def _manual_component(self, submission: Submission, test: Test) -> tuple[float, float, bool]:
        manual_questions = {
            str(q.id): q
            for q in test.questions
            if q.q_type in {QuestionType.ESSAY, QuestionType.SHORT_ANSWER}
        }
        if not manual_questions:
            return 0.0, 0.0, True

        grade_map = {str(g.question_id): float(g.score) for g in submission.manual_grades}
        total = 0.0
        total_max = 0.0
        all_graded = True

        for qid, q in manual_questions.items():
            max_points = max(1.0, float(q.points))
            total_max += max_points
            if qid not in grade_map:
                all_graded = False
                continue
            total += max(0.0, min(max_points, grade_map[qid]))

        return total, total_max, all_graded

    async def _finalize_rasch_for_test(
        self,
        test: Test,
        triggering_submission_id: UUID,
        reviewer_id: UUID,
        override: float | None,
    ) -> None:
        all_rows = await self.repo.list_for_test(test.id)
        objective_questions = [
            q
            for q in test.questions
            if q.q_type in {
                QuestionType.MULTIPLE_CHOICE,
                QuestionType.TRUE_FALSE,
                QuestionType.TWO_PART_WRITTEN,
            }
        ]

        if not objective_questions:
            for row in all_rows:
                manual_total, _, all_graded = self._manual_component(row, test)
                row.final_score = manual_total
                row.status = (
                    SubmissionStatus.COMPLETED if all_graded else SubmissionStatus.PENDING_REVIEW
                )
                if row.status == SubmissionStatus.COMPLETED:
                    row.reviewed_at = datetime.now(UTC)
                    row.review_by = reviewer_id
            return

        item_ids = [str(q.id) for q in objective_questions]
        submission_ids: list[UUID] = []
        matrix: list[list[int]] = []

        for row in all_rows:
            submission_ids.append(row.id)
            row_vector: list[int] = []
            for q in objective_questions:
                ans = row.answers_json.get(str(q.id), "")
                row_vector.append(1 if is_question_correct(q, ans) else 0)
            matrix.append(row_vector)

        estimate = estimate_rasch_1pl(
            submission_ids=submission_ids,
            item_ids=item_ids,
            matrix=matrix,
        )

        objective_points = sum(max(1.0, float(q.points)) for q in objective_questions)
        manual_points = sum(
            max(1.0, float(q.points))
            for q in test.questions
            if q.q_type in {QuestionType.ESSAY, QuestionType.SHORT_ANSWER}
        )
        total_points = objective_points + manual_points
        objective_weight = objective_points / total_points if total_points > 0 else 1.0
        manual_weight = 1.0 - objective_weight

        now = datetime.now(UTC)
        for row in all_rows:
            theta = estimate.theta_by_submission.get(row.id, 0.0)
            rasch_score = theta_to_score_100(theta)
            manual_score, manual_max, all_graded = self._manual_component(row, test)
            manual_percent = (manual_score / manual_max * 100.0) if manual_max > 0 else 0.0

            composite = rasch_score * objective_weight + manual_percent * manual_weight
            row.final_score = round(composite, 4)
            row.status = SubmissionStatus.COMPLETED if all_graded else SubmissionStatus.PENDING_REVIEW
            if row.status == SubmissionStatus.COMPLETED:
                row.reviewed_at = now
                row.review_by = reviewer_id

        if override is not None:
            for row in all_rows:
                if row.id == triggering_submission_id:
                    row.final_score = max(0.0, float(override))
                    row.status = SubmissionStatus.COMPLETED
                    row.reviewed_at = now
                    row.review_by = reviewer_id
                    break
