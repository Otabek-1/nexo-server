from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_refresh_rejects_malformed_token_as_unauthorized(monkeypatch):
    settings = SimpleNamespace(
        jwt_access_ttl_min=15,
        jwt_refresh_ttl_days=30,
        jwt_secret_key="a" * 32,
        jwt_refresh_secret_key="b" * 32,
    )
    monkeypatch.setattr("app.services.auth_service.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    service = AuthService(db=object())

    with pytest.raises(HTTPException) as exc_info:
        await service.refresh("not-a-jwt")

    assert exc_info.value.status_code == 401
