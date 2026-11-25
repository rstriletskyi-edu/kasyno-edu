from fractions import Fraction

from pydantic import ValidationError
import pytest

from src.configs.games.slots import SlotsSettings
from src.services.games.slots_rules import (
    SlotMachineConfig,
    SlotPaytableRule,
    SlotSymbolSpec,
    calculate_theoretical_rtp,
    evaluate_spin,
    get_slots_machine_config,
    pick_symbol_by_roll,
)


def test_default_machine_config_loads_and_has_exact_rtp() -> None:
    machine = get_slots_machine_config()

    assert machine.reels == 3
    assert machine.rows == 1
    assert len(machine.symbols) == 6
    assert machine.total_weight == 100
    assert len(machine.paytable) == 7

    rtp = calculate_theoretical_rtp(machine)
    assert rtp == 0.95256
    assert Fraction(952_560, 1_000_000) == Fraction(rtp).limit_denominator(1_000_000)


@pytest.mark.parametrize(
    ("roll", "expected_id"),
    [
        (0, "cherry"),
        (29, "cherry"),
        (30, "lemon"),
        (54, "lemon"),
        (55, "orange"),
        (74, "orange"),
        (75, "bell"),
        (87, "bell"),
        (88, "star"),
        (95, "star"),
        (96, "seven"),
        (99, "seven"),
    ],
)
def test_pick_symbol_by_roll_boundaries(roll: int, expected_id: str) -> None:
    machine = get_slots_machine_config()
    assert pick_symbol_by_roll(machine, roll).id == expected_id


@pytest.mark.parametrize("bad_roll", [-1, 100, True, False])
def test_pick_symbol_by_roll_rejects_invalid_values(bad_roll: int | bool) -> None:
    machine = get_slots_machine_config()
    with pytest.raises(ValueError):
        pick_symbol_by_roll(machine, bad_roll)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("reel_symbols", "expected_symbol", "expected_count", "expected_multiplier"),
    [
        (["seven", "seven", "seven"], "seven", 3, 500),
        (["star", "star", "star"], "star", 3, 75),
        (["bell", "bell", "bell"], "bell", 3, 30),
        (["orange", "orange", "orange"], "orange", 3, 15),
        (["lemon", "lemon", "lemon"], "lemon", 3, 10),
        (["cherry", "cherry", "cherry"], "cherry", 3, 6),
        (["cherry", "cherry", "lemon"], "cherry", 2, 2),
        (["cherry", "seven", "cherry"], "cherry", 2, 2),
        (["bell", "cherry", "cherry"], "cherry", 2, 2),
    ],
)
def test_evaluate_spin_matches_winning_combinations(
    reel_symbols: list[str],
    expected_symbol: str,
    expected_count: int,
    expected_multiplier: int,
) -> None:
    machine = get_slots_machine_config()
    matched = evaluate_spin(machine, reel_symbols)

    assert matched is not None
    assert matched.symbol == expected_symbol
    assert matched.count == expected_count
    assert matched.multiplier == expected_multiplier


@pytest.mark.parametrize(
    "reel_symbols",
    [
        ["seven", "seven", "lemon"],
        ["star", "star", "cherry"],
        ["cherry", "lemon", "orange"],
        ["bell", "star", "seven"],
    ],
)
def test_evaluate_spin_returns_none_for_losing_spins(reel_symbols: list[str]) -> None:
    machine = get_slots_machine_config()
    assert evaluate_spin(machine, reel_symbols) is None


def test_evaluate_spin_rejects_invalid_reel_inputs() -> None:
    machine = get_slots_machine_config()

    with pytest.raises(ValueError, match="Expected 3 reel symbols"):
        evaluate_spin(machine, ["cherry", "cherry"])
    with pytest.raises(ValueError, match="Unknown reel symbol"):
        evaluate_spin(machine, ["cherry", "diamond", "seven"])


def test_slot_machine_config_validation_rejects_invalid_specs() -> None:
    valid_symbols = (
        SlotSymbolSpec(id="cherry", label="Wiśnia", weight=50),
        SlotSymbolSpec(id="seven", label="Siódemka", weight=50),
    )
    valid_paytable = (SlotPaytableRule(symbol="seven", count=3, multiplier=10, name="777"),)

    with pytest.raises(ValidationError, match="reels=3 and rows=1"):
        SlotMachineConfig(reels=3, rows=3, symbols=valid_symbols, paytable=valid_paytable)

    with pytest.raises(ValidationError, match="Symbol IDs must be unique"):
        SlotMachineConfig(
            reels=3,
            rows=1,
            symbols=(
                SlotSymbolSpec(id="cherry", label="A", weight=50),
                SlotSymbolSpec(id="cherry", label="B", weight=50),
            ),
            paytable=(SlotPaytableRule(symbol="cherry", count=3, multiplier=5, name="3x"),),
        )

    with pytest.raises(ValidationError, match="unknown symbol"):
        SlotMachineConfig(
            reels=3,
            rows=1,
            symbols=valid_symbols,
            paytable=(SlotPaytableRule(symbol="ghost", count=3, multiplier=5, name="Ghost"),),
        )

    with pytest.raises(ValidationError, match="Duplicate paytable rule"):
        SlotMachineConfig(
            reels=3,
            rows=1,
            symbols=valid_symbols,
            paytable=(
                SlotPaytableRule(symbol="seven", count=3, multiplier=10, name="A"),
                SlotPaytableRule(symbol="seven", count=3, multiplier=20, name="B"),
            ),
        )


def test_slots_settings_reads_env_and_validates_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SLOTS_MIN_BET_AMOUNT", "5")
    monkeypatch.setenv("SLOTS_MAX_BET_AMOUNT", "250")
    monkeypatch.setenv("SLOTS_EXPOSE_RTP", "true")

    settings = SlotsSettings(_env_file=None)
    assert settings.min_bet_amount == 5
    assert settings.max_bet_amount == 250
    assert settings.expose_rtp is True

    with pytest.raises(ValidationError):
        SlotsSettings(_env_file=None, min_bet_amount=0)
    with pytest.raises(ValidationError):
        SlotsSettings(_env_file=None, min_bet_amount=100, max_bet_amount=50)
