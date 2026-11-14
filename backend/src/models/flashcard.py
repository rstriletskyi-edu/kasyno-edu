from pydantic import BaseModel


class FlashcardResponse(BaseModel):
    id: str
    question: str
    expected_answer: str
    category: str = "Ogólne"


class FlashcardsResponse(BaseModel):
    items: list[FlashcardResponse]