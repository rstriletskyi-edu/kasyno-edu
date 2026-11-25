import asyncio

import pytest

from src.configs.games.slots import SlotsSettings
from src.models.slots import SlotsSpinRequest
from src.services.games.slots_service import SlotsService
from src.services.user_service import UserService
from src.utils.exceptions import BetLimitExceededError
from tests.fakes.auth import make_user
from tests.fakes.firestore import FakeFirestoreDB


def _settings(**overrides: object) -> SlotsSettings:
    defaults: dict[str, object] = {
        "min_bet_amount": 5,
        "max_bet_amount": 50,
        "expose_rtp": False,
    }
    defaults.update(overrides)
    return SlotsSettings(_env_file=None, **defaults)  # type: ignore[arg-type]


def test_build_config_hides_rtp_and_probabilities_when_disabled() -> None:
    config = SlotsService.build_config(_settings(expose_rtp=False))

    assert config.reels == 3
    assert config.rows == 1
    assert config.min_bet_amount == 5
    assert config.max_bet_amount == 50
    assert config.rtp is None
    assert all(symbol.probability is None for symbol in config.symbols)
    assert len(config.paytable) == 7


def test_build_config_exposes_rtp_and_probabilities_when_enabled() -> None:
    config = SlotsService.build_config(_settings(expose_rtp=True))

    assert config.rtp == 0.95256
    probabilities = [symbol.probability for symbol in config.symbols]
    assert all(p is not None and p > 0 for p in probabilities)
    assert round(sum(p for p in probabilities if p is not None), 6) == 1.0


@pytest.mark.parametrize(
    ("bet_amount", "expected_message"),
    [
        (4, "Bet amount must be at least 5"),
        (51, "Bet amount cannot exceed 50"),
    ],
)
def test_spin_validates_bet_limits_before_rng_or_settlement(
    bet_amount: int,
    expected_message: str,
) -> None:
    db = FakeFirestoreDB(credits=500)
    rng_called = False

    def fail_if_called(_bound: int) -> int:
        nonlocal rng_called
        rng_called = True
        return 0

    service = SlotsService(
        user_service=UserService(db),  # type: ignore[arg-type]
        settings=_settings(),
        rng=fail_if_called,
    )

    with pytest.raises(BetLimitExceededError) as exc_info:
        asyncio.run(service.spin(make_user(), SlotsSpinRequest(bet_amount=bet_amount)))

    assert exc_info.value.detail == expected_message
    assert rng_called is False
    assert db.seen_uids == []


@pytest.mark.parametrize("bad_roll", [-1, 100, True, False])
def test_spin_rejects_invalid_rng_values_before_firestore(bad_roll: int | bool) -> None:
    db = FakeFirestoreDB(credits=500)
    service = SlotsService(
        user_service=UserService(db),  # type: ignore[arg-type]
        settings=_settings(),
        rng=lambda _bound: bad_roll,  # type: ignore[return-value]
    )

    with pytest.raises(ValueError, match="Roll must be an integer"):
        asyncio.run(service.spin(make_user(), SlotsSpinRequest(bet_amount=10)))

    assert db.seen_uids == []


def test_spin_settles_jackpot_and_losing_spins() -> None:
    db = FakeFirestoreDB(credits=500)
    # Roll 99 picks "seven" (weight range [96, 100)) -> 3x seven = 500x multiplier.
    jackpot_service = SlotsService(
        user_service=UserService(db),  # type: ignore[arg-type]
        settings=_settings(),
        rng=lambda _bound: 99,
    )
    jackpot = asyncio.run(jackpot_service.spin(make_user(), SlotsSpinRequest(bet_amount=10)))

    assert jackpot.reels == ["seven", "seven", "seven"]
    assert jackpot.won is True
    assert jackpot.matched_combination is not None
    assert jackpot.matched_combination.multiplier == 500
    assert jackpot.payout == 5000
    assert jackpot.net_profit == 4990
    assert jackpot.new_balance == 5490
    assert db.state["credits"] == 5490

    # Alternating rolls [0 (cherry), 30 (lemon), 55 (orange)] -> losing spin.
    rolls = iter([0, 30, 55])
    losing_service = SlotsService(
        user_service=UserService(db),  # type: ignore[arg-type]
        settings=_settings(),
        rng=lambda _bound: next(rolls),
    )
    loss = asyncio.run(losing_service.spin(make_user(), SlotsSpinRequest(bet_amount=20)))

    assert loss.reels == ["cherry", "lemon", "orange"]
    assert loss.won is False
    assert loss.matched_combination is None
    assert loss.payout == 0
    assert loss.net_profit == -20
    assert loss.new_balance == 5470
    assert db.state["credits"] == 5470
