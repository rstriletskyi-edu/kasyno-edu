from pydantic import BaseModel, ConfigDict, Field, StrictInt

__all__ = [
    "SlotsConfigResponse",
    "SlotsPaytableEntryResponse",
    "SlotsSpinRequest",
    "SlotsSpinResponse",
    "SlotsSymbolResponse",
]


class SlotsSymbolResponse(BaseModel):
    """Public slot symbol metadata; probability is included only when SLOTS_EXPOSE_RTP=true."""

    id: str
    label: str
    probability: float | None = None


class SlotsPaytableEntryResponse(BaseModel):
    """Winning symbol combination and total return multiplier."""

    symbol: str
    count: int
    multiplier: int
    name: str


class SlotsConfigResponse(BaseModel):
    """Public classic 3x1 slot machine configuration and paytable."""

    reels: int
    rows: int
    min_bet_amount: int
    max_bet_amount: int
    symbols: list[SlotsSymbolResponse]
    paytable: list[SlotsPaytableEntryResponse]
    rtp: float | None = None


class SlotsSpinRequest(BaseModel):
    """Wager request for a single classic 3x1 slot spin."""

    model_config = ConfigDict(extra="forbid")

    bet_amount: StrictInt = Field(ge=1)


class SlotsSpinResponse(BaseModel):
    """Server-authoritative outcome of a classic 3x1 slot spin."""

    reels: list[str]
    won: bool
    matched_combination: SlotsPaytableEntryResponse | None
    bet_amount: int
    payout: int
    net_profit: int
    new_balance: int
