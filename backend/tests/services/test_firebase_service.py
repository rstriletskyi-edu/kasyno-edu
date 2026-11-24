from collections.abc import Callable
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.configs.settings import Settings
from src.services import firebase_service
from src.utils.exceptions import FirebaseNotInitializedError


def test_is_firebase_initialized_reflects_get_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.services.firebase_service.firebase_admin.get_app",
        Mock(side_effect=ValueError("no app")),
    )
    assert firebase_service.is_firebase_initialized() is False

    monkeypatch.setattr(
        "src.services.firebase_service.firebase_admin.get_app",
        Mock(return_value=object()),
    )
    assert firebase_service.is_firebase_initialized() is True


@pytest.mark.allow_init_firebase
def test_init_firebase_returns_true_if_already_initialized(
    monkeypatch: pytest.MonkeyPatch,
    make_settings: Callable[..., Settings],
) -> None:
    init_app = Mock()
    monkeypatch.setattr("src.services.firebase_service.is_firebase_initialized", lambda: True)
    monkeypatch.setattr("src.services.firebase_service.firebase_admin.initialize_app", init_app)

    assert firebase_service.init_firebase(make_settings()) is True
    init_app.assert_not_called()


@pytest.mark.allow_init_firebase
def test_init_firebase_returns_false_without_credentials_file(
    monkeypatch: pytest.MonkeyPatch,
    make_settings: Callable[..., Settings],
    tmp_path: Path,
) -> None:
    init_app = Mock()
    monkeypatch.setattr("src.services.firebase_service.is_firebase_initialized", lambda: False)
    monkeypatch.setattr("src.services.firebase_service.firebase_admin.initialize_app", init_app)

    settings = make_settings(firebase_credentials_path=tmp_path / "missing.json")
    assert firebase_service.init_firebase(settings) is False
    init_app.assert_not_called()


@pytest.mark.allow_init_firebase
def test_init_firebase_initializes_sdk_when_credentials_file_exists(
    monkeypatch: pytest.MonkeyPatch,
    make_settings: Callable[..., Settings],
    tmp_path: Path,
) -> None:
    creds_file = tmp_path / "dummy-sa.json"
    creds_file.write_text("{}", encoding="utf-8")

    cert_mock = Mock(return_value="fake-cert")
    init_app = Mock()
    monkeypatch.setattr("src.services.firebase_service.is_firebase_initialized", lambda: False)
    monkeypatch.setattr("src.services.firebase_service.credentials.Certificate", cert_mock)
    monkeypatch.setattr("src.services.firebase_service.firebase_admin.initialize_app", init_app)

    settings = make_settings(
        firebase_credentials_path=creds_file,
        firebase_database_url="https://ci.firebasedatabase.app",
        firebase_project_id="ci-project",
    )

    assert firebase_service.init_firebase(settings) is True
    cert_mock.assert_called_once_with(creds_file)
    init_app.assert_called_once_with(
        "fake-cert",
        {"databaseURL": "https://ci.firebasedatabase.app", "projectId": "ci-project"},
    )


def test_get_firestore_checks_initialization_and_returns_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.firebase_service.is_firebase_initialized", lambda: False)
    with pytest.raises(FirebaseNotInitializedError):
        firebase_service.get_firestore()

    fake_client = object()
    monkeypatch.setattr("src.services.firebase_service.is_firebase_initialized", lambda: True)
    monkeypatch.setattr("src.services.firebase_service.firestore.client", lambda: fake_client)
    assert firebase_service.get_firestore() is fake_client


def test_get_realtime_db_checks_initialization_and_handles_missing_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.firebase_service.is_firebase_initialized", lambda: False)
    with pytest.raises(FirebaseNotInitializedError):
        firebase_service.get_realtime_db()

    monkeypatch.setattr("src.services.firebase_service.is_firebase_initialized", lambda: True)
    monkeypatch.setattr(
        "src.services.firebase_service.db.reference",
        Mock(side_effect=ValueError("missing url")),
    )
    with pytest.raises(FirebaseNotInitializedError, match="Realtime Database URL is not configured"):
        firebase_service.get_realtime_db()

    fake_ref = object()
    monkeypatch.setattr("src.services.firebase_service.db.reference", lambda: fake_ref)
    assert firebase_service.get_realtime_db() is fake_ref
