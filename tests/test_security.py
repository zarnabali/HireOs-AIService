import pytest
from fastapi import HTTPException

from app.core import security
from app.core.config import get_settings


@pytest.mark.asyncio
async def test_require_api_key_rejects_invalid_key(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_service_api_key", "expected-key")

    with pytest.raises(HTTPException) as exc:
        await security.require_api_key(x_api_key="wrong-key")

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_require_api_key_accepts_valid_key(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_service_api_key", "expected-key")

    assert await security.require_api_key(x_api_key="expected-key") is None
