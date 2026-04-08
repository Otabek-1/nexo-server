from fastapi import HTTPException

from app.core.constants import QuestionType, ScoringType
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
