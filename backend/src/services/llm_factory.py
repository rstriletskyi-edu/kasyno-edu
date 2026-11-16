from langchain_core.language_models import BaseChatModel

from src.configs.settings import Settings
from src.utils.exceptions import LlmNotConfiguredError


def build_chat_model(settings: Settings, api_key: str) -> BaseChatModel:
    """Build a chat model for the configured provider.

    ``openai`` also covers OpenAI-compatible hosts when ``llm_base_url`` is set.
    Native ``google_genai`` and ``anthropic`` packages are imported only when selected.
    """
    provider = settings.llm_provider
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        kwargs: dict[str, object] = {
            "model": settings.llm_model,
            "api_key": api_key,
            "temperature": 0,
            "timeout": settings.llm_timeout_seconds,
        }
        if settings.llm_base_url:
            kwargs["base_url"] = settings.llm_base_url
        return ChatOpenAI(**kwargs)

    if provider == "google_genai":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise LlmNotConfiguredError(
                "LLM provider package is not installed: langchain-google-genai"
            ) from exc
        return ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=api_key,
            temperature=0,
            timeout=settings.llm_timeout_seconds,
        )

    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise LlmNotConfiguredError(
                "LLM provider package is not installed: langchain-anthropic"
            ) from exc
        return ChatAnthropic(
            model=settings.llm_model,
            api_key=api_key,
            temperature=0,
            timeout=settings.llm_timeout_seconds,
        )

    raise LlmNotConfiguredError(f"Unsupported LLM provider: {provider}")
