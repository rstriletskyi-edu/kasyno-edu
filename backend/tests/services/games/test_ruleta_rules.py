from fractions import Fraction

import pytest

from src.models.ruleta import BetType, PocketColor
from src.services.games.ruleta_rules import (
    BLACK_NUMBERS,
    GREEN_NUMBERS,
    PAYOUT_MULTIPLIERS,
    RED_NUMBERS,
    WHEEL_ORDER,
    calculate_bet_payout,
    get_pocket_color,
    resolve_covered_numbers,
    validate_bet_combination,
)


# --- 1. Wheel integrity & color partitioning ---


def test_wheel_integrity_and_color_partitioning() -> None:
    assert len(WHEEL_ORDER) == 37
    assert set(WHEEL_ORDER) == set(range(37))
    assert len(RED_NUMBERS) == 18
    assert len(BLACK_NUMBERS) == 18
    assert GREEN_NUMBERS == frozenset({0})
    assert RED_NUMBERS.isdisjoint(BLACK_NUMBERS)
    assert (RED_NUMBERS | BLACK_NUMBERS | GREEN_NUMBERS) == set(range(37))

    assert get_pocket_color(0) == PocketColor.GREEN
    non_zero_colors = [get_pocket_color(n) for n in WHEEL_ORDER if n != 0]
    for idx in range(len(non_zero_colors)):
        assert non_zero_colors[idx] != non_zero_colors[(idx + 1) % len(non_zero_colors)]


# --- 2. Payouts, zero edge cases & RTP ---


@pytest.mark.parametrize(
    ("bet_type", "numbers", "selection", "win_num", "lose_num", "expected_multiplier"),
    [
        (BetType.STRAIGHT, [17], None, 17, 18, 35),
        (BetType.SPLIT, [1, 2], None, 2, 3, 17),
        (BetType.STREET, [4, 5, 6], None, 5, 7, 11),
        (BetType.CORNER, [1, 2, 4, 5], None, 4, 6, 8),
        (BetType.SIX_LINE, [1, 2, 3, 4, 5, 6], None, 6, 7, 5),
        (BetType.DOZEN, None, 2, 13, 12, 2),
        (BetType.COLUMN, None, 3, 36, 35, 2),
        (BetType.RED, None, None, 32, 15, 1),
        (BetType.BLACK, None, None, 15, 32, 1),
        (BetType.EVEN, None, None, 24, 25, 1),
        (BetType.ODD, None, None, 25, 24, 1),
        (BetType.LOW, None, None, 18, 19, 1),
        (BetType.HIGH, None, None, 19, 18, 1),
    ],
)
def test_all_13_bet_types_win_and_lose_payouts(
    bet_type: BetType,
    numbers: list[int] | None,
    selection: int | None,
    win_num: int,
    lose_num: int,
    expected_multiplier: int,
) -> None:
    amount = 10
    won, payout = calculate_bet_payout(bet_type, numbers, selection, amount, win_num)
    assert won is True
    assert payout == amount * (expected_multiplier + 1)
    assert PAYOUT_MULTIPLIERS[bet_type] == expected_multiplier

    lost, zero_payout = calculate_bet_payout(bet_type, numbers, selection, amount, lose_num)
    assert lost is False
    assert zero_payout == 0


@pytest.mark.parametrize(
    ("bet_type", "selection"),
    [
        (BetType.RED, None),
        (BetType.BLACK, None),
        (BetType.EVEN, None),
        (BetType.ODD, None),
        (BetType.LOW, None),
        (BetType.HIGH, None),
        (BetType.DOZEN, 1),
        (BetType.DOZEN, 2),
        (BetType.DOZEN, 3),
        (BetType.COLUMN, 1),
        (BetType.COLUMN, 2),
        (BetType.COLUMN, 3),
    ],
)
def test_zero_loses_all_outside_bets(bet_type: BetType, selection: int | None) -> None:
    won, payout = calculate_bet_payout(bet_type, None, selection, 50, 0)
    assert won is False
    assert payout == 0


@pytest.mark.parametrize(
    ("bet_type", "numbers", "expected_payout"),
    [
        (BetType.STRAIGHT, [0], 360),
        (BetType.SPLIT, [0, 1], 180),
        (BetType.SPLIT, [2, 0], 180),
        (BetType.SPLIT, [0, 3], 180),
        (BetType.STREET, [0, 1, 2], 120),
        (BetType.STREET, [0, 2, 3], 120),
        (BetType.CORNER, [0, 1, 2, 3], 90),
    ],
)
def test_zero_wins_valid_inside_bets_covering_zero(
    bet_type: BetType, numbers: list[int], expected_payout: int
) -> None:
    won, payout = calculate_bet_payout(bet_type, numbers, None, 10, 0)
    assert won is True
    assert payout == expected_payout


@pytest.mark.parametrize(
    ("bet_type", "numbers", "selection"),
    [
        (BetType.STRAIGHT, [7], None),
        (BetType.SPLIT, [7, 8], None),
        (BetType.STREET, [7, 8, 9], None),
        (BetType.CORNER, [7, 8, 10, 11], None),
        (BetType.SIX_LINE, [7, 8, 9, 10, 11, 12], None),
        (BetType.DOZEN, None, 1),
        (BetType.COLUMN, None, 2),
        (BetType.RED, None, None),
        (BetType.BLACK, None, None),
        (BetType.EVEN, None, None),
        (BetType.ODD, None, None),
        (BetType.LOW, None, None),
        (BetType.HIGH, None, None),
    ],
)
def test_exact_european_roulette_rtp_for_every_bet_type(
    bet_type: BetType, numbers: list[int] | None, selection: int | None
) -> None:
    amount = 10
    total_returned = sum(
        calculate_bet_payout(bet_type, numbers, selection, amount, pocket)[1]
        for pocket in range(37)
    )
    assert Fraction(total_returned, 37 * amount) == Fraction(36, 37)


# --- 3. Combination validation ---


def test_valid_inside_bet_numbers_are_normalized_sorted() -> None:
    numbers, selection = validate_bet_combination(BetType.CORNER, [5, 2, 4, 1], None)
    assert numbers == [1, 2, 4, 5]
    assert selection is None
    assert resolve_covered_numbers(BetType.CORNER, [5, 2, 4, 1], None) == frozenset({1, 2, 4, 5})


@pytest.mark.parametrize(
    ("bet_type", "numbers", "selection"),
    [
        (BetType.STRAIGHT, None, None),
        (BetType.STRAIGHT, [37], None),
        (BetType.STRAIGHT, [-1], None),
        (BetType.STRAIGHT, [1, 2], None),
        (BetType.STRAIGHT, [1], 1),
        (BetType.SPLIT, [1, 1], None),
        (BetType.SPLIT, [1, 5], None),
        (BetType.SPLIT, [3, 4], None),  # row boundary wrap is NOT adjacent on layout
        (BetType.STREET, [2, 3, 4], None),  # crosses row boundary
        (BetType.STREET, [0, 1, 3], None),  # 0,1,3 is not a contiguous basket street
        (BetType.CORNER, [2, 3, 5, 7], None),
        (BetType.CORNER, [3, 4, 6, 7], None),  # wraps across columns
        (BetType.SIX_LINE, [2, 3, 4, 5, 6, 7], None),
        (BetType.DOZEN, None, None),
        (BetType.DOZEN, None, 4),
        (BetType.DOZEN, [1], 1),
        (BetType.COLUMN, None, 0),
        (BetType.RED, [1], None),
        (BetType.BLACK, None, 1),
    ],
)
def test_invalid_bet_combinations_are_rejected(
    bet_type: BetType, numbers: list[int] | None, selection: int | None
) -> None:
    with pytest.raises(ValueError):
        validate_bet_combination(bet_type, numbers, selection)
