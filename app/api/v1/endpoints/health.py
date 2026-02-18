from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session

router = APIRouter(tags=["health"])
REQUEST_COUNTER = Counter("nexo_api_requests_total", "Total API requests", ["path"])


@router.get("/health/live")
async def health_live():
    REQUEST_COUNTER.labels(path="/health/live").inc()
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready(db: AsyncSession = Depends(db_session)):
    REQUEST_COUNTER.labels(path="/health/ready").inc()
    await db.execute(text("SELECT 1"))
    return {"status": "ready"}


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

