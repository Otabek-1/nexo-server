import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.telegram_bot_service import TelegramBotService


def test_result_notification_sends_once_and_records_delivery():
    registration = SimpleNamespace(phone_e164="+998901234567", telegram_user_id=12345)
    test = SimpleNamespace(id=7, title="SAT Mock")
    submission = SimpleNamespace(
        id="submission-1",
        participant_attempt_value=registration.phone_e164,
        final_score=1420,
        result_notified_at=None,
    )

    class FakeRepository:
        async def list_for_test(self, test_id):
            assert test_id == test.id
            return [registration]

    class FakeDatabase:
        commits = 0

        async def commit(self):
            self.commits += 1

    service = TelegramBotService.__new__(TelegramBotService)
    service.repo = FakeRepository()
    service.db = FakeDatabase()
    service._send_message = AsyncMock()

    asyncio.run(service.notify_test_results(test, [submission]))
    first_delivery_time = submission.result_notified_at
    asyncio.run(service.notify_test_results(test, [submission]))

    service._send_message.assert_awaited_once_with(
        registration.telegram_user_id,
        "✅ SAT Mock: natijangiz tayyor.\nYakuniy ball: 1420",
    )
    assert first_delivery_time is not None
    assert service.db.commits == 1
