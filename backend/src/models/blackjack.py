from pydantic import BaseModel, ConfigDict, Field, StrictInt

from src.services.games.blackjack_rules import (
    BlackjackAction,
    BlackjackOutcome,
    BlackjackStatus,
    Rank,
    Suit,
)

__all__ = [
    "BlackjackAction",
    "BlackjackGameResponse",
    "BlackjackOutcome",
    "BlackjackStartRequest",
    "BlackjackStatus",
    "CardResponse",
    "Rank",
    "Suit",
]


class CardResponse(BaseModel):
    """Serialized playing card visible to the client."""

    rank: Rank
    suit: Suit


class BlackjackStartRequest(BaseModel):
    """Wager request to start a new Classic Blackjack round."""

    model_config = ConfigDict(extra="forbid")

    bet_amount: StrictInt = Field(ge=1)


class BlackjackGameResponse(BaseModel):
    """Server-authoritative state of a Classic Blackjack round."""

    game_id: str
    status: BlackjackStatus
    outcome: BlackjackOutcome | None
    bet_amount: int
    payout: int
    net_profit: int
    new_balance: int
    player_cards: list[CardResponse]
    player_value: int
    player_is_soft: bool
    dealer_cards: list[CardResponse]
    dealer_value: int
    dealer_hidden_cards: int
    available_actions: list[BlackjackAction]
