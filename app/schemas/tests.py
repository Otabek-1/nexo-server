from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.constants import FieldType, QuestionType, ScoringType, TestType


class ParticipantFieldIn(BaseModel):
    id: str
    label: str = Field(min_length=1, max_length=120)
    type: FieldType
    required: bool = True
    locked: bool = False


class QuestionIn(BaseModel):
    id: str | None = None
    type: QuestionType
    content: str = Field(min_length=1)
    options: list[str] = Field(default_factory=list)
    subQuestions: list[str] = Field(default_factory=list)
    twoPartCorrectAnswers: list[str] = Field(default_factory=list)
    twoPartPoints: list[float] = Field(default_factory=list)
    points: float = 1
    correctAnswer: str = ""

    @field_validator("points")
    @classmethod
    def validate_points(cls, v: float) -> float:
        if v < 0:
            raise ValueError("points must be >= 0")
        return v


class TestDataIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    startTime: datetime
    endTime: datetime
    duration: int = Field(ge=1)
    attemptsCount: int = Field(ge=1)
    scoringType: ScoringType
    testType: TestType
    participantFields: list[ParticipantFieldIn]


class TestCreateRequest(BaseModel):
    testData: TestDataIn
    questions: list[QuestionIn]


class TestPatchRequest(BaseModel):
    testData: TestDataIn | None = None
    questions: list[QuestionIn] | None = None


class TestStatsOut(BaseModel):
    submissionsCount: int
    pendingCount: int


class TestSummaryOut(BaseModel):
    id: int
    testData: dict
    questionsCount: int
    creatorPlan: str
    createdAt: datetime
    stats: TestStatsOut


class QuestionOut(BaseModel):
    id: UUID
    type: str
    content: str
    options: list[str]
    subQuestions: list[str] = Field(default_factory=list)
    twoPartCorrectAnswers: list[str] = Field(default_factory=list)
    twoPartPoints: list[float] = Field(default_factory=list)
    points: float
    correctAnswer: str


class TestDetailOut(BaseModel):
    id: int
    testData: dict
    questions: list[QuestionOut]
    creatorPlan: str
    createdAt: datetime
    hasEssay: bool
    hasOpenQuestions: bool


class SessionConfigOut(BaseModel):
    id: int
    testData: dict
    questions: list[QuestionOut]
    creatorPlan: str
    status: str


class AttemptValidateRequest(BaseModel):
    participant_value: str


class AttemptValidateOut(BaseModel):
    allowed: bool
    used_attempts: int
    max_attempts: int
