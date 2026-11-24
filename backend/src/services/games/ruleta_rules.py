from enum import Enum


class PocketColor(str, Enum):
    """Pocket color on a European Roulette wheel."""

    GREEN = "green"
    RED = "red"
    BLACK = "black"


class BetType(str, Enum):
    """Supported European Roulette bet types."""

    STRAIGHT = "straight"
    SPLIT = "split"
    STREET = "street"
    CORNER = "corner"
    SIX_LINE = "six_line"
    DOZEN = "dozen"
    COLUMN = "column"
    RED = "red"
    BLACK = "black"
    EVEN = "even"
    ODD = "odd"
    LOW = "low"
    HIGH = "high"


WHEEL_ORDER: tuple[int, ...] = (
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
    5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26,
)

RED_NUMBERS: frozenset[int] = frozenset({
    1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36,
})
BLACK_NUMBERS: frozenset[int] = frozenset({
    2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35,
})
GREEN_NUMBERS: frozenset[int] = frozenset({0})

PAYOUT_MULTIPLIERS: dict[BetType, int] = {
    BetType.STRAIGHT: 35,
    BetType.SPLIT: 17,
    BetType.STREET: 11,
    BetType.CORNER: 8,
    BetType.SIX_LINE: 5,
    BetType.DOZEN: 2,
    BetType.COLUMN: 2,
    BetType.RED: 1,
    BetType.BLACK: 1,
    BetType.EVEN: 1,
    BetType.ODD: 1,
    BetType.LOW: 1,
    BetType.HIGH: 1,
}

VALID_STRAIGHTS: frozenset[tuple[int, ...]] = frozenset({(n,) for n in range(37)})
VALID_SPLITS: frozenset[tuple[int, ...]] = frozenset(
    {(0, 1), (0, 2), (0, 3)}
    | {(3 * r + 1, 3 * r + 2) for r in range(12)}
    | {(3 * r + 2, 3 * r + 3) for r in range(12)}
    | {(n, n + 3) for n in range(1, 34)}
)
VALID_STREETS: frozenset[tuple[int, ...]] = frozenset(
    {(0, 1, 2), (0, 2, 3)}
    | {(3 * r + 1, 3 * r + 2, 3 * r + 3) for r in range(12)}
)
VALID_CORNERS: frozenset[tuple[int, ...]] = frozenset(
    {(0, 1, 2, 3)}
    | {(n, n + 1, n + 3, n + 4) for n in range(1, 33) if (n - 1) % 3 in (0, 1)}
)
VALID_SIX_LINES: frozenset[tuple[int, ...]] = frozenset(
    {tuple(range(3 * r + 1, 3 * r + 7)) for r in range(11)}
)

_INSIDE_BET_COMBINATIONS: dict[BetType, frozenset[tuple[int, ...]]] = {
    BetType.STRAIGHT: VALID_STRAIGHTS,
    BetType.SPLIT: VALID_SPLITS,
    BetType.STREET: VALID_STREETS,
    BetType.CORNER: VALID_CORNERS,
    BetType.SIX_LINE: VALID_SIX_LINES,
}

DOZEN_NUMBERS: dict[int, frozenset[int]] = {
    1: frozenset(range(1, 13)),
    2: frozenset(range(13, 25)),
    3: frozenset(range(25, 37)),
}
COLUMN_NUMBERS: dict[int, frozenset[int]] = {
    1: frozenset(range(1, 37, 3)),
    2: frozenset(range(2, 37, 3)),
    3: frozenset(range(3, 37, 3)),
}
EVEN_NUMBERS: frozenset[int] = frozenset(range(2, 37, 2))
ODD_NUMBERS: frozenset[int] = frozenset(range(1, 37, 2))
LOW_NUMBERS: frozenset[int] = frozenset(range(1, 19))
HIGH_NUMBERS: frozenset[int] = frozenset(range(19, 37))

_OUTSIDE_FIXED_SETS: dict[BetType, frozenset[int]] = {
    BetType.RED: RED_NUMBERS,
    BetType.BLACK: BLACK_NUMBERS,
    BetType.EVEN: EVEN_NUMBERS,
    BetType.ODD: ODD_NUMBERS,
    BetType.LOW: LOW_NUMBERS,
    BetType.HIGH: HIGH_NUMBERS,
}

_SELECTION_SETS: dict[BetType, dict[int, frozenset[int]]] = {
    BetType.DOZEN: DOZEN_NUMBERS,
    BetType.COLUMN: COLUMN_NUMBERS,
}


def get_pocket_color(number: int) -> PocketColor:
    """Return the European Roulette color for a pocket number in 0..36."""
    if isinstance(number, bool) or not 0 <= number <= 36:
        raise ValueError(f"Pocket number must be between 0 and 36, got {number}")
    if number in GREEN_NUMBERS:
        return PocketColor.GREEN
    if number in RED_NUMBERS:
        return PocketColor.RED
    return PocketColor.BLACK


def validate_bet_combination(
    bet_type: BetType,
    numbers: list[int] | None,
    selection: int | None,
) -> tuple[list[int] | None, int | None]:
    """Validate and normalize (numbers, selection) for the given European Roulette bet type."""
    if bet_type in _INSIDE_BET_COMBINATIONS:
        if selection is not None:
            raise ValueError(f"Bet type '{bet_type.value}' does not accept 'selection'")
        if not numbers:
            raise ValueError(f"Bet type '{bet_type.value}' requires 'numbers'")
        if len(set(numbers)) != len(numbers):
            raise ValueError("Bet numbers must be unique")
        normalized = tuple(sorted(numbers))
        if normalized not in _INSIDE_BET_COMBINATIONS[bet_type]:
            raise ValueError(
                f"Invalid number combination {list(normalized)} for bet type '{bet_type.value}'"
            )
        return list(normalized), None

    if bet_type in _SELECTION_SETS:
        if numbers is not None:
            raise ValueError(f"Bet type '{bet_type.value}' does not accept 'numbers'")
        if selection not in (1, 2, 3):
            raise ValueError(
                f"Bet type '{bet_type.value}' requires 'selection' to be 1, 2, or 3"
            )
        return None, selection

    if numbers is not None:
        raise ValueError(f"Bet type '{bet_type.value}' does not accept 'numbers'")
    if selection is not None:
        raise ValueError(f"Bet type '{bet_type.value}' does not accept 'selection'")
    return None, None


def resolve_covered_numbers(
    bet_type: BetType,
    numbers: list[int] | None,
    selection: int | None,
) -> frozenset[int]:
    """Return the set of winning pocket numbers covered by a validated bet."""
    normalized_numbers, normalized_selection = validate_bet_combination(
        bet_type, numbers, selection
    )
    if normalized_numbers is not None:
        return frozenset(normalized_numbers)
    if bet_type in _SELECTION_SETS:
        assert normalized_selection is not None
        return _SELECTION_SETS[bet_type][normalized_selection]
    return _OUTSIDE_FIXED_SETS[bet_type]


def calculate_bet_payout(
    bet_type: BetType,
    numbers: list[int] | None,
    selection: int | None,
    amount: int,
    winning_number: int,
) -> tuple[bool, int]:
    """Evaluate a single bet against a winning pocket and return (won, total_payout)."""
    if isinstance(amount, bool) or amount <= 0:
        raise ValueError("Bet amount must be positive")
    get_pocket_color(winning_number)
    covered = resolve_covered_numbers(bet_type, numbers, selection)
    if winning_number in covered:
        return True, amount * (PAYOUT_MULTIPLIERS[bet_type] + 1)
    return False, 0
