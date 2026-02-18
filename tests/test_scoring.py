from app.core.constants import QuestionType, ScoringType, SubmissionStatus
from app.models.domain import Question
from app.services.scoring_service import auto_score_submission
from uuid import UUID


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
