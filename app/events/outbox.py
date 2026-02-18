from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import OutboxEvent


async def push_event(db: AsyncSession, event_type: str, payload: dict) -> OutboxEvent:
    row = OutboxEvent(event_type=event_type, payload_json=payload, status="pending")
    db.add(row)
    await db.flush()
    return row

