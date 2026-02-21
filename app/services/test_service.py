from datetime import UTC, datetime
import json
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
        test_ids = [int(row.id) for row in rows]
        question_counts = await self.repo.question_counts_bulk(test_ids)
        stats_map = await self.repo.submission_stats_bulk(test_ids)
        output = []
        for row in rows:
            total, pending = stats_map.get(int(row.id), (0, 0))
            output.append(
                {
                    "id": row.id,
                    "testData": self._test_data(row),
                    "questionsCount": question_counts.get(int(row.id), 0),
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
        existing_tests_count = await self.repo.count_creator_tests(creator_id)
        if user_plan == PlanCode.FREE and existing_tests_count >= DEFAULT_FREE_LIMITS["activeTests"]:
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
        used_res = await self.db.execute(
            select(func.count(Submission.id)).where(
                Submission.test_id == test_id,
                Submission.participant_attempt_value == participant_value.strip(),
            )
        )
        used = int(used_res.scalar() or 0)
        return {
            "allowed": used < row.attempts_count,
            "used_attempts": used,
            "max_attempts": row.attempts_count,
        }

    def serialize_test_detail(self, row: Test, include_correct: bool = True) -> dict:
        questions = []
        for q in sorted(row.questions, key=lambda item: item.sort_order):
            options = [o.option_html for o in sorted(q.options, key=lambda x: x.option_index)]
            sub_questions: list[str] = []
            two_part_correct_answers: list[str] = []
            two_part_points: list[float] = []
            correct_answer = q.correct_answer_text if include_correct else ""

            if q.q_type == QuestionType.TWO_PART_WRITTEN:
                sub_questions = options[:2]
                while len(sub_questions) < 2:
                    sub_questions.append("")
                first, second, first_points, second_points = self._decode_two_part_payload(q.correct_answer_text)
                two_part_points = [first_points, second_points]
                two_part_correct_answers = [first, second] if include_correct else ["", ""]
                correct_answer = ""

            questions.append(
                {
                    "id": q.id,
                    "type": q.q_type.value,
                    "content": q.content_html,
                    "options": options,
                    "subQuestions": sub_questions,
                    "twoPartCorrectAnswers": two_part_correct_answers,
                    "twoPartPoints": two_part_points,
                    "points": q.points,
                    "correctAnswer": correct_answer,
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
            question_type = item["type"]
            correct_answer_text = str(item.get("correctAnswer", ""))
            q = Question(
                q_type=question_type,
                content_html=sanitize_rich_html(item["content"]),
                points=float(item.get("points", 1) or 1),
                correct_answer_text=correct_answer_text,
                sort_order=idx,
            )

            if question_type == QuestionType.TWO_PART_WRITTEN:
                sub_questions = [str(value or "").strip() for value in item.get("subQuestions", [])][:2]
                while len(sub_questions) < 2:
                    sub_questions.append("")
                for opt_idx, text in enumerate(sub_questions):
                    q.options.append(QuestionOption(option_index=opt_idx, option_html=sanitize_rich_html(text)))

                two_part_answers = [str(value or "").strip() for value in item.get("twoPartCorrectAnswers", [])][:2]
                while len(two_part_answers) < 2:
                    two_part_answers.append("")
                two_part_points = [float(value or 1) for value in item.get("twoPartPoints", [])][:2]
                while len(two_part_points) < 2:
                    two_part_points.append(1.0)
                two_part_points = [value if value > 0 else 1.0 for value in two_part_points]
                q.correct_answer_text = json.dumps(
                    {
                        "first": two_part_answers[0],
                        "second": two_part_answers[1],
                        "firstPoints": two_part_points[0],
                        "secondPoints": two_part_points[1],
                    },
                    ensure_ascii=False,
                )
                q.points = two_part_points[0] + two_part_points[1]
            else:
                for opt_idx, opt in enumerate(item.get("options", [])):
                    if str(opt).strip():
                        q.options.append(QuestionOption(option_index=opt_idx, option_html=sanitize_rich_html(opt)))

            mapped_questions.append(q)
        test.questions = mapped_questions

    def _decode_two_part_payload(self, raw: str) -> tuple[str, str, float, float]:
        try:
            payload = json.loads(str(raw or ""))
            first = str(payload.get("first", "")).strip()
            second = str(payload.get("second", "")).strip()
            first_points = float(payload.get("firstPoints", 1) or 1)
            second_points = float(payload.get("secondPoints", 1) or 1)
            if first_points <= 0:
                first_points = 1.0
            if second_points <= 0:
                second_points = 1.0
            return first, second, first_points, second_points
        except Exception:
            return "", "", 1.0, 1.0
