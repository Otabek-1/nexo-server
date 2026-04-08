from datetime import UTC, datetime
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
from app.repositories.registration_repository import RegistrationRepository
from app.repositories.submission_repository import SubmissionRepository
from app.services.plan_service import PlanService
from app.services.rasch_service import estimate_rasch_1pl, summarize_rasch_items, theta_to_score_100
from app.services.scoring_service import auto_score_submission, is_question_correct, two_part_part_results
from app.services.test_service import TestService
from app.utils.phone import normalize_phone_e164


class SubmissionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SubmissionRepository(db)
        self.registration_repo = RegistrationRepository(db)
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

        full_name = str(participant_values.get("fullName") or "").strip()
        if not full_name:
            raise HTTPException(status_code=400, detail="fullName required")

        if test.attempts_enabled:
            phone = normalize_phone_e164(participant_values.get("phone", ""))
            if not phone:
                raise HTTPException(status_code=400, detail="Telefon raqam +998901234567 formatida bo'lishi kerak")

            registration = await self.registration_repo.get_by_test_and_phone(test_id=test_id, phone_e164=phone)
            if not registration:
                raise HTTPException(status_code=400, detail="Bu telefon raqam test uchun ro'yxatdan o'tmagan")

            attempt_value = phone
            attempts = await self.repo.count_for_attempt_value(test_id=test_id, participant_attempt_value=attempt_value)
            if attempts >= test.attempts_count:
                raise HTTPException(status_code=400, detail="Attempt limit reached")
            secondary = phone
        else:
            attempt_value = full_name
            secondary = str(participant_values.get("phone", "")).strip()

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
            submissions_count = await self.repo.count_for_test(test_id)
            if submissions_count >= DEFAULT_FREE_LIMITS["submissionsPerTest"]:
                raise HTTPException(status_code=400, detail="Free submissionsPerTest limit reached")

        auto_score, auto_max, status = auto_score_submission(
            test.questions, answers, test.scoring_type
        )
        final_score = auto_score if status == SubmissionStatus.COMPLETED else None
        row = Submission(
            test_id=test_id,
            participant_full_name=full_name,
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
        await self._auto_finalize_rasch_if_ready(test)
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
            if override is not None:
                raise HTTPException(status_code=400, detail="Rasch final score override qo'llab-quvvatlanmaydi")
            await self._finalize_rasch_for_test(
                test=test,
                triggering_submission_id=submission_id,
                reviewer_id=user_id,
                override=None,
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
        test = await self.test_service.get_test_or_404(test_id)
        await self._auto_finalize_rasch_if_ready(test)
        rows = await self.repo.list_for_test(test_id, include_manual_grades=False)
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
            "raschStats": self._build_rasch_stats(test=test, rows=rows),
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

    def _build_rasch_stats(self, test: Test, rows: list[Submission]) -> dict | None:
        if test.scoring_type != ScoringType.RASCH or not rows:
            return None

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
            return None

        objective_items: list[dict] = []
        for q in objective_questions:
            if q.q_type == QuestionType.TWO_PART_WRITTEN:
                objective_items.append({"item_id": f"{q.id}:first", "question": q, "part": "first"})
                objective_items.append({"item_id": f"{q.id}:second", "question": q, "part": "second"})
            else:
                objective_items.append({"item_id": str(q.id), "question": q, "part": None})

        item_ids = [item["item_id"] for item in objective_items]
        matrix: list[list[int]] = []
        for row in rows:
            row_vector: list[int] = []
            for item in objective_items:
                q = item["question"]
                ans = row.answers_json.get(str(q.id), "")
                if q.q_type == QuestionType.TWO_PART_WRITTEN:
                    is_first, is_second, _, _ = two_part_part_results(q, ans)
                    row_vector.append(1 if (is_first if item["part"] == "first" else is_second) else 0)
                else:
                    row_vector.append(1 if is_question_correct(q, ans) else 0)
            matrix.append(row_vector)

        item_stats = summarize_rasch_items(item_ids=item_ids, matrix=matrix)
        item_stat_map = {stat.item_id: stat for stat in item_stats}

        question_stats: list[dict] = []
        for q in objective_questions:
            if q.q_type == QuestionType.TWO_PART_WRITTEN:
                related_ids = [f"{q.id}:first", f"{q.id}:second"]
            else:
                related_ids = [str(q.id)]
            related_stats = [item_stat_map[item_id] for item_id in related_ids if item_id in item_stat_map]
            if not related_stats:
                continue
            correct_count = sum(item.correct_count for item in related_stats)
            incorrect_count = sum(item.incorrect_count for item in related_stats)
            total_count = sum(item.total_count for item in related_stats)
            accuracy = (correct_count / total_count) if total_count > 0 else 0.0
            question_stats.append(
                {
                    "questionId": str(q.id),
                    "label": f"{q.sort_order + 1}-savol",
                    "contentPreview": self._question_preview(q.content_html),
                    "correctCount": correct_count,
                    "incorrectCount": incorrect_count,
                    "totalCount": total_count,
                    "accuracy": round(accuracy, 4),
                    "itemCount": len(related_stats),
                }
            )

        if not question_stats:
            return None

        ordered = sorted(
            question_stats,
            key=lambda item: (-float(item["accuracy"]), -int(item["correctCount"]), item["label"]),
        )
        reverse_ordered = sorted(
            question_stats,
            key=lambda item: (float(item["accuracy"]), -int(item["incorrectCount"]), item["label"]),
        )

        return {
            "totalSubmissions": len(rows),
            "easiestQuestion": ordered[0],
            "hardestQuestion": reverse_ordered[0],
            "questionStats": question_stats,
        }

    def _question_preview(self, html: str, limit: int = 140) -> str:
        text = " ".join(str(html or "").replace("<", " <").replace(">", "> ").split())
        cleaned = []
        inside_tag = False
        for ch in text:
            if ch == "<":
                inside_tag = True
                continue
            if ch == ">":
                inside_tag = False
                cleaned.append(" ")
                continue
            if not inside_tag:
                cleaned.append(ch)
        plain = " ".join("".join(cleaned).split())
        if len(plain) <= limit:
            return plain
        return f"{plain[: max(limit - 1, 0)].rstrip()}…"

    async def _auto_finalize_rasch_if_ready(self, test: Test) -> None:
        if test.scoring_type != ScoringType.RASCH:
            return
        if datetime.now(UTC) < test.end_time:
            return

        rows = await self.repo.list_for_test(test.id, include_manual_grades=False)
        if not rows:
            return

        has_pending = any(row.status != SubmissionStatus.COMPLETED or row.final_score is None for row in rows)
        if not has_pending:
            return

        await self._finalize_rasch_for_test(
            test=test,
            triggering_submission_id=rows[0].id,
            reviewer_id=test.creator_id,
            override=None,
        )
        await self.db.commit()

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

        objective_items: list[dict] = []
        for q in objective_questions:
            if q.q_type == QuestionType.TWO_PART_WRITTEN:
                objective_items.append(
                    {"item_id": f"{q.id}:first", "question": q, "part": "first"}
                )
                objective_items.append(
                    {"item_id": f"{q.id}:second", "question": q, "part": "second"}
                )
            else:
                objective_items.append(
                    {"item_id": str(q.id), "question": q, "part": None}
                )

        item_ids = [item["item_id"] for item in objective_items]
        submission_ids: list[UUID] = []
        matrix: list[list[int]] = []

        for row in all_rows:
            submission_ids.append(row.id)
            row_vector: list[int] = []
            for item in objective_items:
                q = item["question"]
                ans = row.answers_json.get(str(q.id), "")
                if q.q_type == QuestionType.TWO_PART_WRITTEN:
                    is_first, is_second, _, _ = two_part_part_results(q, ans)
                    row_vector.append(1 if (is_first if item["part"] == "first" else is_second) else 0)
                else:
                    row_vector.append(1 if is_question_correct(q, ans) else 0)
            matrix.append(row_vector)

        estimate = estimate_rasch_1pl(
            submission_ids=submission_ids,
            item_ids=item_ids,
            matrix=matrix,
        )

        now = datetime.now(UTC)
        for row in all_rows:
            theta = estimate.theta_by_submission.get(row.id, 0.0)
            rasch_score = theta_to_score_100(theta)
            row.final_score = round(rasch_score, 4)
            row.status = SubmissionStatus.COMPLETED
            row.reviewed_at = now
            row.review_by = reviewer_id
