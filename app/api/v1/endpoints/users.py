from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_current_user
from app.schemas.common import CurrentUser
from app.services.plan_service import PlanService

router = APIRouter(tags=["users"])


@router.get("/me", response_model=CurrentUser)
async def get_me(user=Depends(get_current_user), db: AsyncSession = Depends(db_session)):
    service = PlanService(db)
    plan = await service.get_user_plan(user.id)
    return CurrentUser(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        plan=plan.value,
    )

