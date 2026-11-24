from collections.abc import Callable

import pytest

from src.configs.settings import Settings
from src.services.llm.llm_factory import build_chat_model
from src.utils.exceptions import LlmNotConfiguredError


def test_openai_factory_forwards_base_url(
    monkeypatch: pytest.MonkeyPatch,
    make_settings: Callable[..., Settings],
) -> None:
    captured: dict[str, object] = {}

    class FakeChat:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("langchain_openai.ChatOpenAI", FakeChat)

    build_chat_model(
        make_settings(
            llm_provider="openai",
            llm_model="gpt-test",
            llm_base_url="https://example.test/v1",
            llm_timeout_seconds=12,
        ),
        "sk-test",
    )

    assert captured == {
        "model": "gpt-test",
        "api_key": "sk-test",
        "temperature": 0,
        "timeout": 12,
        "base_url": "https://example.test/v1",
    }


def test_ollama_factory_requires_base_url(make_settings: Callable[..., Settings]) -> None:
    with pytest.raises(LlmNotConfiguredError, match="Model URL is required"):
        build_chat_model(make_settings(llm_provider="ollama", llm_base_url=None), "ollama")


def test_factory_rejects_unknown_provider(make_settings: Callable[..., Settings]) -> None:
    with pytest.raises(LlmNotConfiguredError):
        build_chat_model(make_settings(llm_provider="nope"), "sk-test")


def test_factory_reports_missing_optional_provider(
    monkeypatch: pytest.MonkeyPatch,
    make_settings: Callable[..., Settings],
) -> None:
    real_import = __import__

    def guarded(name: str, *args: object, **kwargs: object) -> object:
        if name == "langchain_google_genai" or name.startswith("langchain_google_genai."):
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", guarded)

    with pytest.raises(LlmNotConfiguredError, match="langchain-google-genai"):
        build_chat_model(make_settings(llm_provider="google_genai"), "sk-test")
