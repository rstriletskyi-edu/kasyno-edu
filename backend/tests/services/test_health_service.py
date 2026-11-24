import asyncio
from collections.abc import Callable

import pytest

from src.configs.settings import Settings
from src.services.health_service import HealthService


@pytest.mark.parametrize("firebase_ready", [False, True])
def test_get_health_reports_settings_and_firebase_status(
    monkeypatch: pytest.MonkeyPatch,
    make_settings: Callable[..., Settings],
    firebase_ready: bool,
) -> None:
    monkeypatch.setattr(
        "src.services.health_service.is_firebase_initialized", lambda: firebase_ready
    )
    settings = make_settings(app_name="Kasyno Test", environment="ci")

    result = asyncio.run(HealthService(settings).get_health())

    assert result.status == "ok"
    assert result.app_name == "Kasyno Test"
    assert result.environment == "ci"
    assert result.firebase_initialized is firebase_ready
