from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import TelegramRegistrationState, TestRegistration


class RegistrationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_test_and_phone(self, test_id: int, phone_e164: str) -> TestRegistration | None:
        res = await self.db.execute(
            select(TestRegistration).where(
                TestRegistration.test_id == test_id,
                TestRegistration.phone_e164 == phone_e164,
            )
        )
        return res.scalar_one_or_none()

    async def upsert_registration(
        self,
        test_id: int,
        phone_e164: str,
        telegram_user_id: int,
        telegram_username: str | None,
        telegram_full_name: str | None,
    ) -> TestRegistration:
        existing = await self.db.execute(
            select(TestRegistration).where(
                TestRegistration.test_id == test_id,
                TestRegistration.telegram_user_id == telegram_user_id,
            )
        )
        row = existing.scalar_one_or_none()
        if row:
            row.phone_e164 = phone_e164
            row.telegram_username = telegram_username
            row.telegram_full_name = telegram_full_name
            row.registered_at = datetime.now(UTC)
            await self.db.flush()
            return row

        row = TestRegistration(
            test_id=test_id,
            phone_e164=phone_e164,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            telegram_full_name=telegram_full_name,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def save_pending_state(self, telegram_user_id: int, test_id: int) -> TelegramRegistrationState:
        existing = await self.db.execute(
            select(TelegramRegistrationState).where(
                TelegramRegistrationState.telegram_user_id == telegram_user_id
            )
        )
        row = existing.scalar_one_or_none()
        if row:
            row.test_id = test_id
            row.updated_at = datetime.now(UTC)
            await self.db.flush()
            return row

        row = TelegramRegistrationState(telegram_user_id=telegram_user_id, test_id=test_id)
        self.db.add(row)
        await self.db.flush()
        return row

    async def get_pending_state(self, telegram_user_id: int) -> TelegramRegistrationState | None:
        res = await self.db.execute(
            select(TelegramRegistrationState).where(
                TelegramRegistrationState.telegram_user_id == telegram_user_id
            )
        )
        return res.scalar_one_or_none()

    async def clear_pending_state(self, telegram_user_id: int) -> None:
        await self.db.execute(
            delete(TelegramRegistrationState).where(
                TelegramRegistrationState.telegram_user_id == telegram_user_id
            )
        )
