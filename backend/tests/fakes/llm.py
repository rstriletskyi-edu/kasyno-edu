import asyncio
from datetime import datetime, timedelta

from langchain_core.messages import HumanMessage, SystemMessage

from src.configs.settings import Settings
from src.models.evaluation import LlmGrade, Verdict
from src.models.flashcard import FlashcardResponse
from src.utils.exceptions import NoFlashcardsAvailableError

CARD_QUESTION = "Jaka jest stolica Francji?"
CARD_ANSWER = "Paryż"
GRADING_BODY = {
    "question_id": "card-1",
    "user_answer": "UNTRUSTED-ANSWER-MARKER",
}


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


class FakeFlashcards:
    def get_flashcard_by_id(self, flashcard_id: str) -> FlashcardResponse:
        if flashcard_id == "missing":
            raise NoFlashcardsAvailableError()
        return FlashcardResponse(
            id=flashcard_id,
            question=CARD_QUESTION,
            expected_answer=CARD_ANSWER,
            category="Geografia",
        )


class FakeModel:
    def __init__(self, result: LlmGrade | None = None, delay: float = 0) -> None:
        self.result = result or LlmGrade(
            score=85,
            verdict=Verdict.PARTIAL,
            explanation="Odpowiedź pokrywa część faktów.",
        )
        self.delay = delay
        self.calls = 0
        self.messages: list[SystemMessage | HumanMessage] | None = None
        self.seen_keys: list[str] = []
        self.seen_providers: list[str] = []
        self.seen_models: list[str] = []
        self.seen_base_urls: list[str | None] = []
        self.error: Exception | None = None

    def bind(self, settings: Settings, api_key: str) -> "FakeModel":
        self.seen_keys.append(api_key)
        self.seen_providers.append(settings.llm_provider)
        self.seen_models.append(settings.llm_model)
        self.seen_base_urls.append(settings.llm_base_url)
        return self

    def with_structured_output(self, schema: type[LlmGrade]) -> "FakeModel":
        assert schema is LlmGrade
        return self

    async def ainvoke(self, messages: list[SystemMessage | HumanMessage]) -> LlmGrade:
        self.calls += 1
        self.messages = messages
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.result
