from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.configs.settings import BASE_DIR


class SlotsSettings(BaseSettings):
    """Environment-backed configuration for the classic 3x1 slot machine (Sloty)."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        env_prefix="SLOTS_",
        extra="ignore",
    )

    min_bet_amount: int = Field(default=1, ge=1)
    max_bet_amount: int = Field(default=500, ge=1)
    expose_rtp: bool = False

    @model_validator(mode="after")
    def validate_limit_relationships(self) -> "SlotsSettings":
        if self.min_bet_amount > self.max_bet_amount:
            raise ValueError("SLOTS_MIN_BET_AMOUNT cannot exceed SLOTS_MAX_BET_AMOUNT")
        return self


@lru_cache
def get_slots_settings() -> SlotsSettings:
    return SlotsSettings()
