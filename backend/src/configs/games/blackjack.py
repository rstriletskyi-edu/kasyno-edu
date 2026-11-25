from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.configs.settings import BASE_DIR


class BlackjackSettings(BaseSettings):
    """Environment-backed configuration for Classic Blackjack."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        env_prefix="BLACKJACK_",
        extra="ignore",
    )

    min_bet_amount: int = Field(default=1, ge=1)
    max_bet_amount: int = Field(default=1000, ge=1)
    deck_count: int = Field(default=6, ge=1, le=8)
    session_ttl_seconds: int = Field(default=1800, ge=60)
    max_active_games_per_user: int = Field(default=1, ge=1, le=10)

    @model_validator(mode="after")
    def validate_limit_relationships(self) -> "BlackjackSettings":
        if self.min_bet_amount > self.max_bet_amount:
            raise ValueError(
                "BLACKJACK_MIN_BET_AMOUNT cannot exceed BLACKJACK_MAX_BET_AMOUNT"
            )
        return self


@lru_cache
def get_blackjack_settings() -> BlackjackSettings:
    return BlackjackSettings()
