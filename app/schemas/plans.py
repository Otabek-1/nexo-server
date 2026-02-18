from datetime import datetime

from pydantic import BaseModel


class PlanOut(BaseModel):
    code: str
    limits: dict


class SubscriptionUpgradeRequest(BaseModel):
    plan: str
    billing_cycle: str = "monthly"


class SubscriptionOut(BaseModel):
    plan: str
    status: str
    billing_cycle: str
    started_at: datetime
    ends_at: datetime | None = None

