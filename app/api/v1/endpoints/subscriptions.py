from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_current_user
from app.core.constants import PlanCode
from app.schemas.plans import SubscriptionOut, SubscriptionUpgradeRequest
from app.services.plan_service import PlanService

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.post("/upgrade", response_model=SubscriptionOut)
async def upgrade_subscription(
    payload: SubscriptionUpgradeRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
):
    try:
        code = PlanCode(payload.plan)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Unknown plan") from exc
    service = PlanService(db)
    sub = await service.set_user_plan(user.id, plan_code=code, billing_cycle=payload.billing_cycle)
    await db.commit()
    return SubscriptionOut(
        plan=code.value,
        status=sub.status,
        billing_cycle=sub.billing_cycle,
        started_at=sub.started_at,
        ends_at=sub.ends_at,
    )

