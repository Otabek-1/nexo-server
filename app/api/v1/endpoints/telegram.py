from fastapi import APIRouter, Depends, HTTPException, Request
from json import JSONDecodeError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_current_user
from app.core.config import get_settings
from app.services.telegram_bot_service import TelegramBotService
from app.services.test_service import TestService

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.get("/tests/{test_id}/registration-link")
async def get_registration_link(
    test_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
):
    test_service = TestService(db)
    test = await test_service.get_test_or_404(test_id)
    if test.creator_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    bot = TelegramBotService(db)
    return {"testId": test_id, "registrationLink": bot.registration_link(test_id)}


@router.post("/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request, db: AsyncSession = Depends(db_session)):
    settings = get_settings()
    expected = settings.telegram_webhook_secret
    if expected and secret != expected:
        raise HTTPException(status_code=403, detail="Invalid secret")

    try:
        payload = await request.json()
    except JSONDecodeError:
        return {"ok": True, "ignored": True, "reason": "invalid_json"}
    bot = TelegramBotService(db)
    return await bot.handle_update(payload)
