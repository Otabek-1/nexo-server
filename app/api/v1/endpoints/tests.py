from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_current_user, get_current_user_optional, get_idempotency_key
from app.core.ratelimit import rate_limit
from app.schemas.common import APIMessage
from app.schemas.submissions import (
    FinalizeRequest,
    LeaderboardResponse,
    ManualGradesPatchRequest,
    SubmissionCreateRequest,
    SubmissionOut,
)
from app.schemas.tests import (
    AttemptValidateOut,
    AttemptValidateRequest,
    SessionConfigOut,
    TestCreateRequest,
    TestDetailOut,
    TestPatchRequest,
    TestSummaryOut,
)
from app.services.submission_service import SubmissionService
from app.services.test_service import TestService

router = APIRouter(prefix="/tests", tags=["tests"])


@router.get("", response_model=list[TestSummaryOut])
async def list_tests(user=Depends(get_current_user), db: AsyncSession = Depends(db_session)):
    service = TestService(db)
    return await service.list_creator_tests(user.id)


@router.post("", response_model=TestDetailOut)
async def create_test(payload: TestCreateRequest, user=Depends(get_current_user), db: AsyncSession = Depends(db_session)):
    service = TestService(db)
    return await service.create_test(user.id, payload.model_dump())


@router.get("/{test_id}", response_model=TestDetailOut)
async def get_test(
    test_id: int,
    user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(db_session),
):
    service = TestService(db)
    row = await service.get_test_or_404(test_id)
    if not user or row.creator_id != user.id:
        return service.serialize_test_detail(row, include_correct=False)
    return service.serialize_test_detail(row, include_correct=True)


@router.patch("/{test_id}", response_model=TestDetailOut)
async def patch_test(
    test_id: int, payload: TestPatchRequest, user=Depends(get_current_user), db: AsyncSession = Depends(db_session)
):
    service = TestService(db)
    return await service.patch_test(test_id, user.id, payload.model_dump(exclude_none=True))


@router.delete("/{test_id}", response_model=APIMessage)
async def delete_test(test_id: int, user=Depends(get_current_user), db: AsyncSession = Depends(db_session)):
    service = TestService(db)
    await service.delete_test(test_id, user.id)
    return APIMessage(message="Test deleted")


@router.post("/{test_id}/publish-link")
async def publish_link(test_id: int, request: Request):
    return {
        "test_id": test_id,
        "public_url": f"{request.base_url}test/{test_id}",
    }


@router.get("/{test_id}/session-config", response_model=SessionConfigOut)
async def session_config(test_id: int, db: AsyncSession = Depends(db_session)):
    service = TestService(db)
    return await service.session_config(test_id)


@router.post("/{test_id}/attempts/validate", response_model=AttemptValidateOut)
async def validate_attempt(
    test_id: int, payload: AttemptValidateRequest, db: AsyncSession = Depends(db_session)
):
    service = TestService(db)
    return await service.validate_attempt(test_id, payload.participant_value)


@router.post("/{test_id}/submissions", response_model=SubmissionOut)
async def create_submission(
    test_id: int,
    payload: SubmissionCreateRequest,
    request: Request,
    db: AsyncSession = Depends(db_session),
    idem_key: str | None = Depends(get_idempotency_key),
):
    rate_limit(key=f"submit:{request.client.host}:{test_id}", limit=25, window_seconds=60)
    service = SubmissionService(db)
    return await service.create_submission(
        test_id=test_id,
        participant_values=payload.participant_values,
        answers=payload.answers,
        idempotency_key=idem_key,
    )


@router.get("/{test_id}/submissions", response_model=list[SubmissionOut])
async def list_submissions(
    test_id: int,
    status: str | None = None,
    latest: int | None = None,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
):
    service = SubmissionService(db)
    return await service.list_submissions(test_id=test_id, user_id=user.id, status=status, latest=latest)


@router.patch("/{test_id}/submissions/{submission_id}/manual-grades", response_model=SubmissionOut)
async def patch_manual_grades(
    test_id: int,
    submission_id: UUID,
    payload: ManualGradesPatchRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
):
    service = SubmissionService(db)
    return await service.patch_manual_grades(
        test_id=test_id, submission_id=submission_id, user_id=user.id, grades=payload.grades
    )


@router.post("/{test_id}/submissions/{submission_id}/finalize", response_model=SubmissionOut)
async def finalize_submission(
    test_id: int,
    submission_id: UUID,
    payload: FinalizeRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
):
    service = SubmissionService(db)
    return await service.finalize_submission(
        test_id=test_id,
        submission_id=submission_id,
        user_id=user.id,
        override=payload.final_score_override,
    )


@router.get("/{test_id}/leaderboard", response_model=LeaderboardResponse)
async def leaderboard(test_id: int, db: AsyncSession = Depends(db_session)):
    service = SubmissionService(db)
    return await service.leaderboard(test_id)
