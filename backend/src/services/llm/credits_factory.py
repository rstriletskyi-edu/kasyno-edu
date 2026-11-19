from collections.abc import Callable

from src.utils.exceptions import LlmNotConfiguredError

CreditsCalculator = Callable[[int], int]


def linear_credits(score: int) -> int:
    """Map a 0–100 score onto 0–10 credits."""
    clamped = max(0, min(100, score))
    return clamped * 10 // 100


_ENGINES: dict[str, CreditsCalculator] = {
    "linear": linear_credits,
}


def build_credits_calculator(engine: str = "linear") -> CreditsCalculator:
    """Return the credits engine selected by name.

    Register another callable in ``_ENGINES`` and set ``CREDITS_ENGINE`` to switch.
    """
    calculator = _ENGINES.get(engine.strip().lower())
    if calculator is None:
        raise LlmNotConfiguredError(f"Unsupported credits engine: {engine}")
    return calculator
