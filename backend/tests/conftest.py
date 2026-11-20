import os

import pytest

# Settings are built when src.main is imported, which happens during collection,
# before fixtures run. These stand-ins satisfy the required fields without a project.
os.environ["FIREBASE_DATABASE_URL"] = "https://test.firebasedatabase.app"
os.environ["QUESTIONS_PATH"] = "questions"


@pytest.fixture(autouse=True)
def mock_firebase(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.main.init_firebase", lambda settings: False)
    monkeypatch.setattr("src.services.firebase_service.init_firebase", lambda settings: False)
