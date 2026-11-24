from enum import StrEnum


class Role(StrEnum):
    CREATOR = "creator"
    ADMIN = "admin"


class PlanCode(StrEnum):
    FREE = "free"
    PRO = "pro"
    LIFETIME = "lifetime"


class ScoringType(StrEnum):
    CLASSIC = "correct-incorrect"
    RASCH = "rasch"
    IRT = "irt"


class TestType(StrEnum):
    EXAM = "exam"
    OLYMPIAD = "olympiad"
    TEST = "test"
    SAT = "sat"


class QuestionType(StrEnum):
    SHORT_ANSWER = "short-answer"
    TWO_PART_WRITTEN = "two-part-written"
    TWO_PART_MATH = "two-part-math"
    MULTIPLE_CHOICE = "multiple-choice"
    ESSAY = "essay"
    TRUE_FALSE = "true-false"


class FieldType(StrEnum):
    TEXT = "text"
    EMAIL = "email"
    TEL = "tel"
    TEXTAREA = "textarea"


class SubmissionStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    COMPLETED = "completed"


DEFAULT_FREE_LIMITS = {
    "activeTests": 3,
    "questionsPerTest": 30,
    "submissionsPerTest": 100,
    "manualReviewRecent": 20,
}
