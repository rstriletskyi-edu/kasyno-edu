from collections import Counter
from functools import lru_cache
from itertools import product
import math
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_MACHINE_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "configs" / "games" / "slots_machine.json"
)


class SlotSymbolSpec(BaseModel):
    """Single symbol definition and reel weight."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    weight: int = Field(ge=1)


class SlotPaytableRule(BaseModel):
    """Winning symbol count rule and total payout multiplier."""

    model_config = ConfigDict(frozen=True)

    symbol: str = Field(min_length=1)
    count: int = Field(ge=2)
    multiplier: int = Field(ge=1)
    name: str = Field(min_length=1)


class SlotMachineConfig(BaseModel):
    """Validated classic 3x1 slot machine specification."""

    model_config = ConfigDict(frozen=True)

    reels: int = Field(ge=1)
    rows: int = Field(default=1, ge=1)
    symbols: tuple[SlotSymbolSpec, ...] = Field(min_length=1)
    paytable: tuple[SlotPaytableRule, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_machine(self) -> "SlotMachineConfig":
        if self.reels != 3 or self.rows != 1:
            raise ValueError("Classic Jednoręki bandyta requires reels=3 and rows=1")

        symbol_ids = [symbol.id for symbol in self.symbols]
        if len(set(symbol_ids)) != len(symbol_ids):
            raise ValueError("Symbol IDs must be unique")

        known_symbols = set(symbol_ids)
        seen_rules: set[tuple[str, int]] = set()
        for rule in self.paytable:
            if rule.symbol not in known_symbols:
                raise ValueError(f"Paytable references unknown symbol '{rule.symbol}'")
            if not 2 <= rule.count <= self.reels:
                raise ValueError(
                    f"Paytable count {rule.count} must be between 2 and {self.reels}"
                )
            key = (rule.symbol, rule.count)
            if key in seen_rules:
                raise ValueError(f"Duplicate paytable rule for {key}")
            seen_rules.add(key)

        return self

    @property
    def total_weight(self) -> int:
        return sum(symbol.weight for symbol in self.symbols)

    def symbol_probabilities(self) -> dict[str, float]:
        total = self.total_weight
        return {symbol.id: round(symbol.weight / total, 6) for symbol in self.symbols}


def load_slots_machine_config(
    path: Path = DEFAULT_MACHINE_CONFIG_PATH,
) -> SlotMachineConfig:
    """Load and validate slot machine specification from JSON."""
    return SlotMachineConfig.model_validate_json(path.read_text(encoding="utf-8"))


@lru_cache
def get_slots_machine_config() -> SlotMachineConfig:
    return load_slots_machine_config()


def pick_symbol_by_roll(machine: SlotMachineConfig, roll: int) -> SlotSymbolSpec:
    """Select a symbol using an integer roll in [0, machine.total_weight)."""
    total = machine.total_weight
    if isinstance(roll, bool) or not 0 <= roll < total:
        raise ValueError(f"Roll must be an integer in [0, {total}), got {roll}")

    cumulative = 0
    for symbol in machine.symbols:
        cumulative += symbol.weight
        if roll < cumulative:
            return symbol

    raise AssertionError("Unreachable cumulative weight fallback")


def evaluate_spin(
    machine: SlotMachineConfig,
    reel_symbols: list[str],
) -> SlotPaytableRule | None:
    """Return the highest-paying matching rule for the spun reel symbols, or None."""
    if len(reel_symbols) != machine.reels:
        raise ValueError(f"Expected {machine.reels} reel symbols, got {len(reel_symbols)}")

    known_symbols = {symbol.id for symbol in machine.symbols}
    unknown = [symbol_id for symbol_id in reel_symbols if symbol_id not in known_symbols]
    if unknown:
        raise ValueError(f"Unknown reel symbol(s): {unknown}")

    counts = Counter(reel_symbols)
    matching = [
        rule for rule in machine.paytable if counts[rule.symbol] >= rule.count
    ]
    if not matching:
        return None
    return max(matching, key=lambda rule: rule.multiplier)


def calculate_theoretical_rtp(machine: SlotMachineConfig) -> float:
    """Compute exact theoretical Return-To-Player across all reel combinations."""
    weighted_return = 0
    for combo in product(machine.symbols, repeat=machine.reels):
        matched = evaluate_spin(machine, [symbol.id for symbol in combo])
        if matched is not None:
            weighted_return += math.prod(symbol.weight for symbol in combo) * matched.multiplier

    total_outcomes = machine.total_weight ** machine.reels
    return round(weighted_return / total_outcomes, 6)
