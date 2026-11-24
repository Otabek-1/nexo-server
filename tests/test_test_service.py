from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.core.constants import QuestionType, ScoringType
from app.core.constants import TestType as AssessmentType
from app.models.domain import Question, QuestionOption
from app.services.test_service import TestService


def test_rasch_rejects_open_questions():
    service = TestService(None)

    questions = [
        {
            "type": QuestionType.ESSAY.value,
            "content": "Essay",
            "points": 5,
            "correctAnswer": "",
            "options": [],
        }
    ]

    try:
        service._validate_rasch_configuration(ScoringType.RASCH, questions)
    except HTTPException as error:
        assert error.status_code == 400
        assert "Rasch tests faqat" in str(error.detail)
    else:
        raise AssertionError("Expected HTTPException for invalid Rasch question type")


def test_rasch_rejects_non_unit_objective_points():
    service = TestService(None)

    questions = [
        {
            "type": QuestionType.MULTIPLE_CHOICE.value,
            "content": "MC",
            "points": 3,
            "correctAnswer": "0",
            "options": ["A", "B"],
        }
    ]

    try:
        service._validate_rasch_configuration(ScoringType.RASCH, questions)
    except HTTPException as error:
        assert error.status_code == 400
        assert "ball 1 bo'lishi kerak" in str(error.detail)
    else:
        raise AssertionError("Expected HTTPException for invalid Rasch points")


def test_rasch_accepts_two_part_math_with_unit_part_points():
    service = TestService(None)

    questions = [
        {
            "type": QuestionType.TWO_PART_MATH.value,
            "content": "Math",
            "points": 2,
            "subQuestions": ["a", "b"],
            "twoPartCorrectAnswers": ["sqrt(2)", "x^2"],
            "twoPartPoints": [1, 1],
            "options": [],
            "correctAnswer": "",
        }
    ]

    service._validate_rasch_configuration(ScoringType.RASCH, questions)


def test_module_timing_sets_total_duration_and_ignores_final_break():
    service = TestService(None)
    modules = service._normalize_modules(
        [
            {"id": "rw", "durationMinutes": 32, "breakAfterMinutes": 10},
            {"id": "math", "durationMinutes": 35, "breakAfterMinutes": 10},
        ]
    )

    assert service._effective_duration(3, modules) == 77


def test_module_timing_counts_only_one_adaptive_easy_or_hard_branch():
    service = TestService(None)
    modules = service._normalize_modules(
        [
            {
                "id": "math-1",
                "title": "Module 1",
                "subject": "math",
                "difficulty": "medium",
                "durationMinutes": 32,
                "breakAfterMinutes": 1,
                "routing": "adaptive",
            },
            {
                "id": "math-2-easy",
                "title": "Module 2 easy",
                "subject": "math",
                "difficulty": "easy",
                "durationMinutes": 32,
                "breakAfterMinutes": 10,
            },
            {
                "id": "math-2-hard",
                "title": "Module 2 hard",
                "subject": "math",
                "difficulty": "hard",
                "durationMinutes": 32,
                "breakAfterMinutes": 10,
            },
        ]
    )

    assert service._effective_duration(107, modules) == 65


def test_duration_without_modules_remains_unchanged():
    service = TestService(None)

    assert service._effective_duration("45", []) == 45


@pytest.mark.asyncio
async def test_replacing_question_options_deletes_old_rows_before_reinserting():
    question_id = UUID("00000000-0000-0000-0000-000000000001")
    question = Question(
        id=question_id,
        q_type=QuestionType.MULTIPLE_CHOICE,
        content_html="Old question",
        points=1,
        correct_answer_text="0",
        sort_order=0,
        options=[QuestionOption(option_index=0, option_html="Old option")],
    )

    class FakeSession:
        flush_count = 0

        async def flush(self):
            assert question.options == []
            self.flush_count += 1

    session = FakeSession()
    service = TestService(session)
    test = SimpleNamespace(questions=[question])

    await service._replace_questions(
        test,
        [
            {
                "id": str(question_id),
                "type": QuestionType.MULTIPLE_CHOICE.value,
                "content": "Updated question",
                "points": 1,
                "correctAnswer": "0",
                "options": ["New option A", "New option B"],
            }
        ],
    )

    assert session.flush_count == 1
    assert [option.option_index for option in question.options] == [0, 1]


def test_irt_and_sat_require_telegram_registration():
    service = TestService(None)

    assert service._requires_telegram_registration(ScoringType.IRT, AssessmentType.EXAM)
    assert service._requires_telegram_registration(ScoringType.CLASSIC, AssessmentType.SAT)
    assert not service._requires_telegram_registration(ScoringType.CLASSIC, AssessmentType.EXAM)


def test_sat_requires_irt_scoring():
    service = TestService(None)

    try:
        service._validate_test_mode(ScoringType.CLASSIC, AssessmentType.SAT)
    except HTTPException as error:
        assert error.status_code == 400
        assert "IRT scoring" in error.detail
    else:
        raise AssertionError("Expected SAT scoring validation error")


def test_sat_math_validation_accepts_comma_separated_short_numeric_variants():
    service = TestService(None)
    service._validate_sat_math_answers(
        [
            {
                "type": QuestionType.SAT_MATH_INPUT.value,
                "correctAnswer": "0.3, 0.33, 0.333, 1/3",
            }
        ]
    )


@pytest.mark.parametrize("correct_answer", ["", "0.3,,1/3", "123456", "answer", "1/1234", "1/0"])
def test_sat_math_validation_rejects_empty_or_invalid_long_variants(correct_answer):
    service = TestService(None)
    with pytest.raises(HTTPException) as error:
        service._validate_sat_math_answers(
            [{"type": QuestionType.SAT_MATH_INPUT.value, "correctAnswer": correct_answer}]
        )
    assert error.value.status_code == 400
