from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import DEFAULT_FREE_LIMITS, PlanCode, QuestionType
from app.models.domain import ParticipantField, Question, QuestionOption, Submission, Test
from app.repositories.test_repository import TestRepository
from app.services.plan_service import PlanService
from app.utils.html import sanitize_rich_html


class TestService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = TestRepository(db)
        self.plan_service = PlanService(db)

    async def list_creator_tests(self, creator_id: UUID) -> list[dict]:
        rows = await self.repo.list_creator_tests(creator_id)
        output = []
        for row in rows:
            total, pending = await self.repo.stats(row.id)
            output.append(
                {
                    "id": row.id,
                    "testData": self._test_data(row),
                    "questionsCount": len(row.questions),
                    "creatorPlan": row.creator_plan_snapshot.value,
                    "createdAt": row.created_at,
                    "stats": {"submissionsCount": total, "pendingCount": pending},
                }
            )
        return output

    async def get_test_or_404(self, test_id: int) -> Test:
        row = await self.repo.get_by_id(test_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
        return row

    async def create_test(self, creator_id: UUID, payload: dict) -> dict:
        user_plan = await self.plan_service.get_user_plan(creator_id)
        existing_tests = await self.repo.list_creator_tests(creator_id)
        if user_plan == PlanCode.FREE and len(existing_tests) >= DEFAULT_FREE_LIMITS["activeTests"]:
            raise HTTPException(status_code=400, detail="Free activeTests limit reached")

        test_data = payload["testData"]
        questions = payload["questions"]
        if user_plan == PlanCode.FREE and len(questions) > DEFAULT_FREE_LIMITS["questionsPerTest"]:
            raise HTTPException(status_code=400, detail="Free questionsPerTest limit reached")

        row = Test(
            creator_id=creator_id,
            title=test_data["title"].strip(),
            description=test_data.get("description", ""),
            start_time=test_data["startTime"],
            end_time=test_data["endTime"],
            duration_minutes=int(test_data["duration"]),
            attempts_count=int(test_data["attemptsCount"]),
            scoring_type=test_data["scoringType"],
            test_type=test_data["testType"],
            creator_plan_snapshot=user_plan,
        )
        self._replace_participant_fields(row, test_data.get("participantFields", []))
        self._replace_questions(row, questions)
        await self.repo.add(row)
        await self.db.commit()

        row = await self.get_test_or_404(row.id)
        return self.serialize_test_detail(row)

    async def patch_test(self, test_id: int, creator_id: UUID, payload: dict) -> dict:
        row = await self.get_test_or_404(test_id)
        if row.creator_id != creator_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        test_data = payload.get("testData")
        questions = payload.get("questions")
        if test_data:
            row.title = test_data["title"].strip()
            row.description = test_data.get("description", "")
            row.start_time = test_data["startTime"]
            row.end_time = test_data["endTime"]
            row.duration_minutes = int(test_data["duration"])
            row.attempts_count = int(test_data["attemptsCount"])
            row.scoring_type = test_data["scoringType"]
            row.test_type = test_data["testType"]
            self._replace_participant_fields(row, test_data.get("participantFields", []))
        if questions is not None:
            self._replace_questions(row, questions)
        await self.db.commit()
        updated = await self.get_test_or_404(test_id)
        return self.serialize_test_detail(updated)

    async def delete_test(self, test_id: int, creator_id: UUID) -> None:
        row = await self.get_test_or_404(test_id)
        if row.creator_id != creator_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        await self.repo.delete(row)
        await self.db.commit()

    async def session_config(self, test_id: int) -> dict:
        row = await self.get_test_or_404(test_id)
        now = datetime.now(UTC)
        status_txt = "active"
        if now < row.start_time:
            status_txt = "pending"
        elif now >= row.end_time:
            status_txt = "ended"
        detail = self.serialize_test_detail(row, include_correct=False)
        return {
            "id": detail["id"],
            "testData": detail["testData"],
            "questions": detail["questions"],
            "creatorPlan": detail["creatorPlan"],
            "status": status_txt,
        }

    async def validate_attempt(self, test_id: int, participant_value: str) -> dict:
        row = await self.get_test_or_404(test_id)
        count_q = await self.db.execute(
            select(Submission).where(
                Submission.test_id == test_id,
                Submission.participant_attempt_value == participant_value.strip(),
            )
        )
        used = len(count_q.scalars().all())
        return {
            "allowed": used < row.attempts_count,
            "used_attempts": used,
            "max_attempts": row.attempts_count,
        }

    def serialize_test_detail(self, row: Test, include_correct: bool = True) -> dict:
        questions = []
        for q in sorted(row.questions, key=lambda item: item.sort_order):
            questions.append(
                {
                    "id": q.id,
                    "type": q.q_type.value,
                    "content": q.content_html,
                    "options": [o.option_html for o in sorted(q.options, key=lambda x: x.option_index)],
                    "points": q.points,
                    "correctAnswer": q.correct_answer_text if include_correct else "",
                }
            )
        has_essay = any(q["type"] == QuestionType.ESSAY.value for q in questions)
        has_open = any(
            q["type"] in {QuestionType.ESSAY.value, QuestionType.SHORT_ANSWER.value} for q in questions
        )
        return {
            "id": row.id,
            "testData": self._test_data(row),
            "questions": questions,
            "creatorPlan": row.creator_plan_snapshot.value,
            "createdAt": row.created_at,
            "hasEssay": has_essay,
            "hasOpenQuestions": has_open,
        }

    def _test_data(self, row: Test) -> dict:
        fields = sorted(row.participant_fields, key=lambda f: f.sort_order)
        return {
            "title": row.title,
            "description": row.description,
            "startTime": row.start_time,
            "endTime": row.end_time,
            "duration": row.duration_minutes,
            "attemptsCount": row.attempts_count,
            "scoringType": row.scoring_type.value,
            "testType": row.test_type.value,
            "participantFields": [
                {
                    "id": f.field_key,
                    "label": f.label,
                    "type": f.field_type.value,
                    "required": f.required,
                    "locked": f.locked,
                }
                for f in fields
            ],
        }

    def _replace_participant_fields(self, test: Test, fields: list[dict]) -> None:
        mapped_fields: list[ParticipantField] = []
        for idx, item in enumerate(fields):
            mapped_fields.append(
                ParticipantField(
                    field_key=item["id"],
                    label=item["label"].strip(),
                    field_type=item["type"],
                    required=item.get("required", True),
                    locked=item.get("locked", False),
                    sort_order=idx,
                ),
            )
        test.participant_fields = mapped_fields

    def _replace_questions(self, test: Test, questions: list[dict]) -> None:
        mapped_questions: list[Question] = []
        for idx, item in enumerate(questions):
            q = Question(
                q_type=item["type"],
                content_html=sanitize_rich_html(item["content"]),
                points=float(item.get("points", 1) or 1),
                correct_answer_text=str(item.get("correctAnswer", "")),
                sort_order=idx,
            )
            for opt_idx, opt in enumerate(item.get("options", [])):
                if str(opt).strip():
                    q.options.append(QuestionOption(option_index=opt_idx, option_html=sanitize_rich_html(opt)))
            mapped_questions.append(q)
        test.questions = mapped_questions
