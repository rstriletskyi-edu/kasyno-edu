import asyncio

import pytest

from src.configs.games.ruleta import RuletaSettings
from src.models.ruleta import BetType, PocketColor, RuletaBetRequest, RuletaSpinRequest
from src.services.games.ruleta_service import RuletaService
from src.services.user_service import UserService
from src.utils.exceptions import BetLimitExceededError
from tests.fakes.auth import make_user
from tests.fakes.firestore import FakeFirestoreDB


def _settings(**overrides: object) -> RuletaSettings:
    defaults: dict[str, object] = {
        "min_bet_amount": 5,
        "max_bet_amount": 50,
        "max_total_bet": 80,
        "max_bets_per_spin": 2,
    }
    defaults.update(overrides)
    return RuletaSettings(_env_file=None, **defaults)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("bets", "expected_message"),
    [
        ([RuletaBetRequest(bet_type=BetType.RED, amount=4)], "Bet amount must be at least 5"),
        ([RuletaBetRequest(bet_type=BetType.RED, amount=51)], "Bet amount cannot exceed 50"),
        (
            [
                RuletaBetRequest(bet_type=BetType.RED, amount=45),
                RuletaBetRequest(bet_type=BetType.BLACK, amount=40),
            ],
            "Total bet 85 exceeds maximum allowed (80)",
        ),
        (
            [
                RuletaBetRequest(bet_type=BetType.RED, amount=10),
                RuletaBetRequest(bet_type=BetType.EVEN, amount=10),
                RuletaBetRequest(bet_type=BetType.LOW, amount=10),
            ],
            "Number of bets exceeds maximum allowed (2)",
        ),
    ],
)
def test_spin_validates_table_limits_before_settlement(
    bets: list[RuletaBetRequest],
    expected_message: str,
) -> None:
    db = FakeFirestoreDB(credits=500)
    service = RuletaService(
        user_service=UserService(db),  # type: ignore[arg-type]
        settings=_settings(),
        rng=lambda: 7,
    )

    with pytest.raises(BetLimitExceededError) as exc_info:
        asyncio.run(service.spin(make_user(), RuletaSpinRequest(bets=bets)))

    assert exc_info.value.detail == expected_message
    assert db.seen_uids == []


@pytest.mark.parametrize("bad_number", [-1, 37, True, False])
def test_spin_rejects_invalid_rng_values(bad_number: int | bool) -> None:
    db = FakeFirestoreDB(credits=500)
    service = RuletaService(
        user_service=UserService(db),  # type: ignore[arg-type]
        settings=_settings(),
        rng=lambda: bad_number,  # type: ignore[return-value]
    )
    payload = RuletaSpinRequest(bets=[RuletaBetRequest(bet_type=BetType.RED, amount=10)])

    with pytest.raises(ValueError, match="RNG produced invalid pocket number"):
        asyncio.run(service.spin(make_user(), payload))

    assert db.seen_uids == []


def test_spin_calculates_payout_and_settles_balance() -> None:
    db = FakeFirestoreDB(credits=500)
    service = RuletaService(
        user_service=UserService(db),  # type: ignore[arg-type]
        settings=_settings(),
        rng=lambda: 0,
    )
    payload = RuletaSpinRequest(
        bets=[
            RuletaBetRequest(bet_type=BetType.STRAIGHT, numbers=[0], amount=10),
            RuletaBetRequest(bet_type=BetType.RED, amount=20),
        ]
    )

    result = asyncio.run(service.spin(make_user(), payload))

    assert result.winning_number == 0
    assert result.color == PocketColor.GREEN
    assert result.total_bet == 30
    assert result.total_payout == 360
    assert result.net_profit == 330
    assert result.new_balance == 830
    assert db.state["credits"] == 830
    assert [b.won for b in result.bets] == [True, False]
