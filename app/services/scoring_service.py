import json
import re

from sympy import SympifyError, simplify
from sympy.parsing.sympy_parser import (
    T,
    convert_xor,
    function_exponentiation,
    implicit_multiplication_application,
    parse_expr,
)

from app.core.constants import QuestionType, ScoringType, SubmissionStatus
from app.models.domain import Question

APOSTROPHE_REGEX = re.compile(r"[\u02BB\u02BC\u2018\u2019`\u00B4]")
MATH_SYMBOL_REGEX = re.compile(r"[\u221A\u221E\u03C0\u222B\u2264\u2265\u2260\u00B1]")
MATH_REPLACEMENTS = {
    "\u2212": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u00D7": "*",
    "\u00B7": "*",
    "\u00F7": "/",
    "\u2044": "/",
    "\u03C0": "pi",
    "\u221E": "oo",
    "\u2264": "<=",
    "\u2265": ">=",
    "\u2260": "!=",
}
SYMPY_TRANSFORMATIONS = T[:] + (
    implicit_multiplication_application,
    convert_xor,
    function_exponentiation,
)


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


def _normalize_math_text(value: str | int | float) -> str:
    text = APOSTROPHE_REGEX.sub("'", str(value or "")).strip()
    if not text:
        return ""
    text = text.replace("\u00a0", " ")
    for source, target in MATH_REPLACEMENTS.items():
        text = text.replace(source, target)
    text = re.sub(r"\bln\b", "log", text, flags=re.IGNORECASE)
    text = re.sub(r"\btg\b", "tan", text, flags=re.IGNORECASE)
    text = re.sub(r"\bctg\b", "cot", text, flags=re.IGNORECASE)
    text = re.sub(r"\bctan\b", "cot", text, flags=re.IGNORECASE)
    text = re.sub(r"\barcsin\b", "asin", text, flags=re.IGNORECASE)
    text = re.sub(r"\barccos\b", "acos", text, flags=re.IGNORECASE)
    text = re.sub(r"\barctg\b", "atan", text, flags=re.IGNORECASE)
    text = re.sub(r"\barctan\b", "atan", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\u221A\s*\(([^()]+)\)", r"sqrt(\1)", text)
    text = re.sub(r"\u221A\s*([A-Za-z0-9.]+)", r"sqrt(\1)", text)
    return text.strip()


def _looks_like_math(value: str) -> bool:
    lowered = value.lower()
    if any(token in lowered for token in ("sqrt", "sin", "cos", "tan", "cot", "log", "ln", "pi", "oo")):
        return True
    return bool(MATH_SYMBOL_REGEX.search(value) or re.search(r"[\^*/=()]", value))


def _parse_math_expression(value: str):
    normalized = _normalize_math_text(value)
    if not normalized:
        return None
    return parse_expr(
        normalized,
        transformations=SYMPY_TRANSFORMATIONS,
        evaluate=True,
        local_dict={},
    )


def _same_math_answer(left: str, right: str) -> bool:
    left_normalized = _normalize_math_text(left)
    right_normalized = _normalize_math_text(right)
    if not left_normalized or not right_normalized:
        return left_normalized == right_normalized

    try:
        left_expr = _parse_math_expression(left_normalized)
        right_expr = _parse_math_expression(right_normalized)
        if left_expr is None or right_expr is None:
            return left_normalized == right_normalized
        return bool(simplify(left_expr - right_expr) == 0)
    except (SympifyError, TypeError, ValueError):
        return left_normalized == right_normalized


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


def _normalize_multiple_choice_value(value: str | int | float) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    upper = raw.upper()
    if len(upper) == 1 and "A" <= upper <= "Z":
        return str(ord(upper) - ord("A"))
    try:
        numeric = int(float(raw))
        return str(numeric)
    except Exception:
        return raw


def _normalize_true_false_value(value: str | int | float) -> str:
    raw = _normalize_text(value).strip()
    if raw in {"true", "1", "yes", "ha", "togri", "to'g'ri"}:
        return "true"
    if raw in {"false", "0", "no", "yoq", "yo'q", "notogri", "noto'g'ri"}:
        return "false"
    return raw


def _is_two_part_question(question: Question) -> bool:
    return question.q_type in {QuestionType.TWO_PART_WRITTEN, QuestionType.TWO_PART_MATH}


def canonicalize_answers(
    questions: list[Question], answers: dict[str, str | int | float]
) -> tuple[dict[str, str | int | float], bool]:
    normalized_answers = {str(key): value for key, value in (answers or {}).items()}
    ordered_questions = sorted(questions, key=lambda item: item.sort_order)
    question_ids = [str(question.id) for question in ordered_questions]
    matched_count = sum(1 for question_id in question_ids if question_id in normalized_answers)

    if matched_count == len(question_ids) or matched_count > 0:
        return normalized_answers, False

    if len(normalized_answers) != len(question_ids):
        return normalized_answers, False

    remapped: dict[str, str | int | float] = {}
    values_in_order = list(normalized_answers.values())
    for index, question in enumerate(ordered_questions):
        remapped[str(question.id)] = values_in_order[index]
    return remapped, True


def is_question_correct(question: Question, raw_answer: str | int | float) -> bool:
    if _is_two_part_question(question):
        user_first, user_second = _parse_two_part_payload(raw_answer)
        correct_first, correct_second, _, _ = _parse_two_part_correct(question.correct_answer_text)
        if question.q_type == QuestionType.TWO_PART_MATH:
            return _same_math_answer(user_first, correct_first) and _same_math_answer(user_second, correct_second)
        return _same_cell_answer(user_first, correct_first) and _same_cell_answer(user_second, correct_second)
    if question.q_type == QuestionType.MULTIPLE_CHOICE:
        return _normalize_multiple_choice_value(raw_answer) == _normalize_multiple_choice_value(question.correct_answer_text)
    if question.q_type == QuestionType.TRUE_FALSE:
        return _normalize_true_false_value(raw_answer) == _normalize_true_false_value(question.correct_answer_text)
    if _looks_like_math(str(raw_answer or "")) or _looks_like_math(str(question.correct_answer_text or "")):
        return _same_math_answer(str(raw_answer or ""), str(question.correct_answer_text or ""))
    return str(raw_answer) == str(question.correct_answer_text)


def two_part_part_results(question: Question, raw_answer: str | int | float) -> tuple[bool, bool, float, float]:
    user_first, user_second = _parse_two_part_payload(raw_answer)
    correct_first, correct_second, first_points, second_points = _parse_two_part_correct(question.correct_answer_text)
    if question.q_type == QuestionType.TWO_PART_MATH:
        return (
            _same_math_answer(user_first, correct_first),
            _same_math_answer(user_second, correct_second),
            first_points,
            second_points,
        )
    return (
        _same_cell_answer(user_first, correct_first),
        _same_cell_answer(user_second, correct_second),
        first_points,
        second_points,
    )


def question_max_score(question: Question, scoring_type: ScoringType) -> float:
    if scoring_type == ScoringType.RASCH or question.q_type == QuestionType.ESSAY:
        if _is_two_part_question(question):
            _, _, first_points, second_points = _parse_two_part_correct(question.correct_answer_text)
            return first_points + second_points
        return max(float(question.points), 1)
    if question.q_type in {
        QuestionType.MULTIPLE_CHOICE,
        QuestionType.TRUE_FALSE,
        QuestionType.TWO_PART_WRITTEN,
        QuestionType.TWO_PART_MATH,
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
        if _is_two_part_question(q) and scoring_type == ScoringType.RASCH:
            is_first, is_second, first_points, second_points = two_part_part_results(q, raw_answer)
            if is_first:
                auto_score += first_points
            if is_second:
                auto_score += second_points
        elif is_question_correct(q, raw_answer):
            auto_score += max_score

    status = SubmissionStatus.PENDING_REVIEW if requires_manual else SubmissionStatus.COMPLETED
    return auto_score, auto_max, status
