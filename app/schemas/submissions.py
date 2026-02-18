from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SubmissionCreateRequest(BaseModel):
    participant_values: dict[str, str]
    answers: dict[str, str | int | float]


class SubmissionParticipantOut(BaseModel):
    fullName: str
    phone: str
    fields: dict[str, str]
    attemptValue: str


class SubmissionOut(BaseModel):
    id: UUID
    testId: int
    participant: SubmissionParticipantOut
    answers: dict[str, str | int | float]
    autoScore: float
    autoMaxScore: float
    finalScore: float | None
    status: str
    submittedAt: datetime
    manualGrades: dict[str, float]
    reviewedAt: datetime | None


class ManualGradesPatchRequest(BaseModel):
    grades: dict[str, float] = Field(default_factory=dict)


class FinalizeRequest(BaseModel):
    final_score_override: float | None = None


class LeaderboardItem(BaseModel):
    id: UUID
    participant: SubmissionParticipantOut
    finalScore: float
    submittedAt: datetime


class PendingItem(BaseModel):
    id: UUID
    participant: SubmissionParticipantOut
    submittedAt: datetime
    status: str


class LeaderboardResponse(BaseModel):
    ranked: list[LeaderboardItem]
    pending: list[PendingItem]
    stats: dict[str, int]

