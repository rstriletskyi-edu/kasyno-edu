from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from src.services.games.ruleta_rules import (
    BetType,
    PocketColor,
    validate_bet_combination,
)

__all__ = [
    "BetType",
    "PocketColor",
    "RuletaBetRequest",
    "RuletaBetResultResponse",
    "RuletaSpinRequest",
    "RuletaSpinResponse",
]


class RuletaBetRequest(BaseModel):
    """Single European Roulette table bet."""

    model_config = ConfigDict(extra="forbid")

    bet_type: BetType
    amount: StrictInt = Field(ge=1)
    numbers: list[StrictInt] | None = None
    selection: StrictInt | None = None

    @model_validator(mode="after")
    def validate_combination(self) -> "RuletaBetRequest":
        normalized_numbers, normalized_selection = validate_bet_combination(
            self.bet_type, self.numbers, self.selection
        )
        self.numbers = normalized_numbers
        self.selection = normalized_selection
        return self


class RuletaSpinRequest(BaseModel):
    """Batch of bets placed on a single European Roulette spin."""

    model_config = ConfigDict(extra="forbid")

    bets: list[RuletaBetRequest] = Field(min_length=1)


class RuletaBetResultResponse(BaseModel):
    """Outcome of an individual bet on a spin."""

    bet_type: BetType
    numbers: list[int] | None
    selection: int | None
    amount: int
    won: bool
    payout: int


class RuletaSpinResponse(BaseModel):
    """Server-authoritative outcome of a European Roulette spin."""

    winning_number: int
    color: PocketColor
    total_bet: int
    total_payout: int
    net_profit: int
    new_balance: int
    bets: list[RuletaBetResultResponse]
