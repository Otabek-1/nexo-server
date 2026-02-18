from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.schemas.plans import PlanOut
from app.services.plan_service import PlanService

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=list[PlanOut])
async def get_plans(db: AsyncSession = Depends(db_session)):
    service = PlanService(db)
    rows = await service.get_available()
    return [PlanOut(code=item.code.value, limits=item.limits) for item in rows]

