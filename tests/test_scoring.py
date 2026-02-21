from app.core.constants import QuestionType, ScoringType, SubmissionStatus
from app.models.domain import Question
from app.services.scoring_service import auto_score_submission
from uuid import UUID
import json


def make_question(q_type: QuestionType, correct: str = "", points: float = 1):
    q = Question(
        q_type=q_type,
        content_html="q",
        points=points,
        correct_answer_text=correct,
        sort_order=0,
        test_id=1,
    )
    q.id = UUID("00000000-0000-0000-0000-000000000001")
    return q


def test_auto_score_for_mc():
    q = make_question(QuestionType.MULTIPLE_CHOICE, correct="1")
    score, max_score, status = auto_score_submission(
        [q], {"00000000-0000-0000-0000-000000000001": "1"}, ScoringType.CLASSIC
    )
    assert score == 1
    assert max_score == 1
    assert status == SubmissionStatus.COMPLETED


def test_manual_required_for_essay():
    q = make_question(QuestionType.ESSAY, points=5)
    score, max_score, status = auto_score_submission(
        [q], {"00000000-0000-0000-0000-000000000001": "text"}, ScoringType.CLASSIC
    )
    assert score == 0
    assert max_score == 0
    assert status == SubmissionStatus.PENDING_REVIEW


def test_auto_score_for_two_part_written():
    q = make_question(
        QuestionType.TWO_PART_WRITTEN,
        correct=json.dumps({"first": "bo'shang", "second": "tamga"}),
    )
    answer = json.dumps({"first": "bo'shang", "second": "tamga"})
    score, max_score, status = auto_score_submission(
        [q], {"00000000-0000-0000-0000-000000000001": answer}, ScoringType.CLASSIC
    )
    assert score == 1
    assert max_score == 1
    assert status == SubmissionStatus.COMPLETED


def test_rasch_two_part_partial_points():
    q = make_question(
        QuestionType.TWO_PART_WRITTEN,
        correct=json.dumps(
            {"first": "alpha", "second": "beta", "firstPoints": 2.0, "secondPoints": 1.0}
        ),
        points=3,
    )
    answer = json.dumps({"first": "alpha", "second": "wrong"})
    score, max_score, status = auto_score_submission(
        [q], {"00000000-0000-0000-0000-000000000001": answer}, ScoringType.RASCH
    )
    assert score == 2.0
    assert max_score == 3.0
    assert status == SubmissionStatus.PENDING_REVIEW
