from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.configs.settings import BASE_DIR


class RuletaSettings(BaseSettings):
    """Environment-backed configuration for European Roulette table limits."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        env_prefix="RULETA_",
        extra="ignore",
    )

    min_bet_amount: int = Field(default=1, ge=1)
    max_bet_amount: int = Field(default=1000, ge=1)
    max_total_bet: int = Field(default=5000, ge=1)
    max_bets_per_spin: int = Field(default=20, ge=1)

    @model_validator(mode="after")
    def validate_limit_relationships(self) -> "RuletaSettings":
        if self.min_bet_amount > self.max_bet_amount:
            raise ValueError("RULETA_MIN_BET_AMOUNT cannot exceed RULETA_MAX_BET_AMOUNT")
        if self.max_bet_amount > self.max_total_bet:
            raise ValueError("RULETA_MAX_BET_AMOUNT cannot exceed RULETA_MAX_TOTAL_BET")
        return self


@lru_cache
def get_ruleta_settings() -> RuletaSettings:
    return RuletaSettings()
