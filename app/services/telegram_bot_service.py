from datetime import UTC, datetime, timedelta
import logging
from urllib.parse import quote_plus

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.domain import Submission, Test
from app.repositories.registration_repository import RegistrationRepository
from app.services.test_service import TestService
from app.utils.phone import normalize_phone_e164

logger = logging.getLogger(__name__)


class TelegramBotService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.repo = RegistrationRepository(db)
        self.test_service = TestService(db)

    def registration_link(self, test_id: int) -> str:
        username = self.settings.telegram_bot_username.lstrip("@")
        if not username:
            return ""
        payload = f"test_{test_id}"
        return f"https://t.me/{username}?start={quote_plus(payload)}"

    async def _send_message(self, chat_id: int, text: str, request_contact: bool = False) -> None:
        token = self.settings.telegram_bot_token
        if not token:
            raise RuntimeError("Telegram bot token is not configured")
        payload: dict = {"chat_id": chat_id, "text": text}
        if request_contact:
            payload["reply_markup"] = {
                "keyboard": [[{"text": "Telefon raqamni yuborish", "request_contact": True}]],
                "resize_keyboard": True,
                "one_time_keyboard": True,
            }
        else:
            payload["reply_markup"] = {"remove_keyboard": True}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload)
            response.raise_for_status()
            result = response.json()
            if not result.get("ok"):
                raise RuntimeError(f"Telegram sendMessage failed: {result.get('description', 'unknown error')}")

    async def notify_test_results(self, test: Test, submissions: list[Submission]) -> None:
        registrations = await self.repo.list_for_test(test.id)
        registrations_by_phone = {row.phone_e164: row for row in registrations}
        sent_any = False

        for submission in submissions:
            if submission.final_score is None or submission.result_notified_at is not None:
                continue
            registration = registrations_by_phone.get(submission.participant_attempt_value)
            if registration is None:
                logger.warning(
                    "Cannot notify submission %s: no Telegram registration for test %s",
                    submission.id,
                    test.id,
                )
                continue

            message = (
                f"✅ {test.title}: natijangiz tayyor.\n"
                f"Yakuniy ball: {submission.final_score:g}"
            )
            try:
                await self._send_message(registration.telegram_user_id, message)
            except (httpx.HTTPError, RuntimeError, ValueError) as error:
                logger.warning(
                    "Telegram result notification failed for submission %s: %s",
                    submission.id,
                    error,
                )
                continue

            submission.result_notified_at = datetime.now(UTC)
            sent_any = True

        if sent_any:
            await self.db.commit()

    async def handle_update(self, update: dict) -> dict:
        message = update.get("message") or {}
        from_user = message.get("from") or {}
        if not message or not from_user:
            return {"ok": True, "ignored": True}

        user_id = int(from_user.get("id"))
        chat_id = int(message.get("chat", {}).get("id", user_id))
        text = str(message.get("text") or "").strip()
        contact = message.get("contact")

        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            payload = parts[1].strip() if len(parts) > 1 else ""
            if payload.startswith("test_"):
                try:
                    test_id = int(payload.removeprefix("test_"))
                except ValueError:
                    await self._send_message(chat_id, "Noto'g'ri test kodi.")
                    return {"ok": True}

                test = await self.test_service.get_test_or_404(test_id)
                if not test.attempts_enabled:
                    await self._send_message(chat_id, "Bu testda Telegram ro'yxatdan o'tish talab qilinmaydi.")
                    return {"ok": True}

                if test.registration_window_hours:
                    deadline = test.created_at + timedelta(hours=int(test.registration_window_hours))
                    if datetime.now(UTC) > deadline:
                        await self._send_message(chat_id, "Bu test uchun ro'yxatdan o'tish muddati yopilgan.")
                        return {"ok": True}

                await self.repo.save_pending_state(user_id, test_id)
                await self.db.commit()
                await self._send_message(
                    chat_id,
                    f"Test #{test_id} uchun ro'yxatdan o'tish boshlandi. Telefon raqamingizni +998... formatda yuboring yoki tugmani bosing.",
                    request_contact=True,
                )
                return {"ok": True}

            await self._send_message(chat_id, "Ro'yxatdan o'tish uchun test havolasidagi bot linkidan kiring.")
            return {"ok": True}

        if contact:
            pending = await self.repo.get_pending_state(user_id)
            if not pending:
                await self._send_message(chat_id, "Avval test havolasidagi /start orqali ro'yxatdan o'tishni boshlang.")
                return {"ok": True}

            phone = normalize_phone_e164(contact.get("phone_number", ""))
            if not phone:
                await self._send_message(chat_id, "Telefon raqam noto'g'ri. +998901234567 formatida yuboring.")
                return {"ok": True}

            test = await self.test_service.get_test_or_404(int(pending.test_id))
            if test.registration_window_hours:
                deadline = test.created_at + timedelta(hours=int(test.registration_window_hours))
                if datetime.now(UTC) > deadline:
                    await self._send_message(chat_id, "Ro'yxatdan o'tish muddati yopilgan.")
                    return {"ok": True}

            full_name = " ".join(
                [str(from_user.get("first_name") or "").strip(), str(from_user.get("last_name") or "").strip()]
            ).strip()
            await self.repo.upsert_registration(
                test_id=int(pending.test_id),
                phone_e164=phone,
                telegram_user_id=user_id,
                telegram_username=from_user.get("username"),
                telegram_full_name=full_name or None,
            )
            await self.repo.clear_pending_state(user_id)
            await self.db.commit()
            await self._send_message(
                chat_id,
                f"Ro'yxatdan o'tish muvaffaqiyatli. Testga kirishda shu telefon raqamni kiriting: {phone}. Uni eslab qoling.",
            )
            return {"ok": True}

        return {"ok": True, "ignored": True}
