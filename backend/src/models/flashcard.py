from pydantic import BaseModel, Field


class RandomFlashcardRequest(BaseModel):
    excluded_ids: list[str] = Field(default_factory=list, max_length=5_000)

class FlashcardResponse(BaseModel):
    id: str
    question: str
    expected_answer: str
    category: str = "Ogólne"