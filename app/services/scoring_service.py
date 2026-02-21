import json
import re

from app.core.constants import QuestionType, ScoringType, SubmissionStatus
from app.models.domain import Question

APOSTROPHE_REGEX = re.compile(r"[\u02BB\u02BC\u2018\u2019`\u00B4]")


def _normalize_text(value: str) -> str:
    return APOSTROPHE_REGEX.sub("'", str(value or "")).lower()


def _tokenize_cells(value: str) -> list[str]:
    source = _normalize_text(value).replace("\u00a0", " ")
    tokens: list[str] = []
    i = 0
    while i < len(source):
        ch = source[i]
        if ch.isspace():
            if tokens and tokens[-1] != " ":
                tokens.append(" ")
            i += 1
            continue
        if ch.isdigit():
            tokens.append(ch)
            i += 1
            continue
        if ch in {"o", "g"} and i + 1 < len(source) and source[i + 1] == "'":
            tokens.append(f"{ch}'")
            i += 2
            continue
        if "a" <= ch <= "z":
            tokens.append(ch)
            i += 1
            continue
        i += 1

    while tokens and tokens[0] == " ":
        tokens.pop(0)
    while tokens and tokens[-1] == " ":
        tokens.pop()
    return tokens


def _same_cell_answer(left: str, right: str) -> bool:
    a = _tokenize_cells(left)
    b = _tokenize_cells(right)
    return len(a) == len(b) and all(x == y for x, y in zip(a, b))


def _parse_two_part_payload(raw: str | int | float) -> tuple[str, str]:
    try:
        payload = json.loads(str(raw or ""))
    except Exception:
        return "", ""
    return str(payload.get("first", "")), str(payload.get("second", ""))


def _parse_two_part_correct(raw: str) -> tuple[str, str, float, float]:
    try:
        payload = json.loads(str(raw or ""))
    except Exception:
        return "", "", 1.0, 1.0
    first = str(payload.get("first", ""))
    second = str(payload.get("second", ""))
    first_points = float(payload.get("firstPoints", 1) or 1)
    second_points = float(payload.get("secondPoints", 1) or 1)
    if first_points <= 0:
        first_points = 1.0
    if second_points <= 0:
        second_points = 1.0
    return first, second, first_points, second_points


def is_question_correct(question: Question, raw_answer: str | int | float) -> bool:
    if question.q_type == QuestionType.TWO_PART_WRITTEN:
        user_first, user_second = _parse_two_part_payload(raw_answer)
        correct_first, correct_second, _, _ = _parse_two_part_correct(question.correct_answer_text)
        return _same_cell_answer(user_first, correct_first) and _same_cell_answer(user_second, correct_second)
    return str(raw_answer) == str(question.correct_answer_text)


def two_part_part_results(question: Question, raw_answer: str | int | float) -> tuple[bool, bool, float, float]:
    user_first, user_second = _parse_two_part_payload(raw_answer)
    correct_first, correct_second, first_points, second_points = _parse_two_part_correct(question.correct_answer_text)
    return (
        _same_cell_answer(user_first, correct_first),
        _same_cell_answer(user_second, correct_second),
        first_points,
        second_points,
    )


def question_max_score(question: Question, scoring_type: ScoringType) -> float:
    if scoring_type == ScoringType.RASCH or question.q_type == QuestionType.ESSAY:
        if question.q_type == QuestionType.TWO_PART_WRITTEN:
            _, _, first_points, second_points = _parse_two_part_correct(question.correct_answer_text)
            return first_points + second_points
        return max(float(question.points), 1)
    if question.q_type in {
        QuestionType.MULTIPLE_CHOICE,
        QuestionType.TRUE_FALSE,
        QuestionType.TWO_PART_WRITTEN,
    }:
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
        if q.q_type == QuestionType.TWO_PART_WRITTEN and scoring_type == ScoringType.RASCH:
            is_first, is_second, first_points, second_points = two_part_part_results(q, raw_answer)
            if is_first:
                auto_score += first_points
            if is_second:
                auto_score += second_points
        elif is_question_correct(q, raw_answer):
            auto_score += max_score

    status = SubmissionStatus.PENDING_REVIEW if requires_manual else SubmissionStatus.COMPLETED
    return auto_score, auto_max, status
