from app.core.constants import QuestionType, ScoringType, SubmissionStatus
from app.models.domain import Question


def question_max_score(question: Question, scoring_type: ScoringType) -> float:
    if scoring_type == ScoringType.RASCH or question.q_type == QuestionType.ESSAY:
        return max(float(question.points), 1)
    if question.q_type in {QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE}:
        return 1
    return 0


def auto_score_submission(
    questions: list[Question], answers: dict[str, str | int | float], scoring_type: ScoringType
) -> tuple[float, float, SubmissionStatus]:
    auto_score = 0.0
    auto_max = 0.0
    requires_manual = scoring_type == ScoringType.RASCH

    for q in questions:
        if q.q_type in {QuestionType.ESSAY, QuestionType.SHORT_ANSWER}:
            requires_manual = True
            continue
        max_score = question_max_score(q, scoring_type)
        auto_max += max_score
        raw_answer = answers.get(str(q.id), "")
        if str(raw_answer) == str(q.correct_answer_text):
            auto_score += max_score

    status = SubmissionStatus.PENDING_REVIEW if requires_manual else SubmissionStatus.COMPLETED
    return auto_score, auto_max, status

