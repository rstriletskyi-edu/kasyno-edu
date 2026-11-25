import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from src.configs.games.blackjack import BlackjackSettings
from src.models.blackjack import (
    BlackjackAction,
    BlackjackOutcome,
    BlackjackStartRequest,
    BlackjackStatus,
)
from src.services.games.blackjack_rules import Card, Rank, Suit
from src.services.games.blackjack_service import BlackjackService, BlackjackSessionStore
from src.services.user_service import UserService
from src.utils.exceptions import (
    BetLimitExceededError,
    BlackjackActiveGameExistsError,
    BlackjackGameNotFoundError,
    BlackjackInvalidActionError,
    InsufficientCreditsError,
)
from tests.fakes.auth import make_user
from tests.fakes.firestore import FakeFirestoreDB


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


def c(rank: Rank, suit: Suit = Suit.SPADES) -> Card:
    return Card(rank=rank, suit=suit)


def _settings(**overrides: object) -> BlackjackSettings:
    defaults: dict[str, object] = {
        "min_bet_amount": 5,
        "max_bet_amount": 200,
        "deck_count": 6,
        "session_ttl_seconds": 1800,
        "max_active_games_per_user": 1,
    }
    defaults.update(overrides)
    return BlackjackSettings(_env_file=None, **defaults)  # type: ignore[arg-type]


def _make_service(
    credits: int = 500,
    cards: list[Card] | None = None,
    settings: BlackjackSettings | None = None,
    clock: MutableClock | None = None,
) -> tuple[BlackjackService, FakeFirestoreDB, MutableClock]:
    db = FakeFirestoreDB(credits=credits)
    used_clock = clock or MutableClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    store = BlackjackSessionStore(clock=used_clock)
    scripted = list(cards or ([c(Rank.TEN), c(Rank.SIX)] * 20))
    service = BlackjackService(
        user_service=UserService(db),  # type: ignore[arg-type]
        settings=settings or _settings(),
        store=store,
        deck_factory=lambda _decks: list(scripted),
    )
    return service, db, used_clock


def test_natural_player_blackjack_resolves_atomically_at_3_to_2() -> None:
    # Deal: p1=A, d1=9, p2=K, d2=8
    service, db, _clock = _make_service(
        credits=500,
        cards=[c(Rank.ACE), c(Rank.NINE), c(Rank.KING), c(Rank.EIGHT)],
    )

    res = asyncio.run(service.start(make_user(), BlackjackStartRequest(bet_amount=20)))

    assert res.status == BlackjackStatus.FINISHED
    assert res.outcome == BlackjackOutcome.PLAYER_BLACKJACK
    assert res.payout == 50
    assert res.net_profit == 30
    assert res.new_balance == 530
    assert res.dealer_hidden_cards == 0
    assert len(res.dealer_cards) == 2
    assert res.available_actions == []
    assert db.state["credits"] == 530
    assert [doc["value"] for _id, doc in db.state["transactions"]] == [-20.0, 50.0]


def test_dealer_blackjack_and_mutual_blackjack_push() -> None:
    # Dealer BJ: p1=10, d1=A, p2=9, d2=Q
    svc_loss, db_loss, _ = _make_service(
        credits=500,
        cards=[c(Rank.TEN), c(Rank.ACE), c(Rank.NINE), c(Rank.QUEEN)],
    )
    loss = asyncio.run(svc_loss.start(make_user(), BlackjackStartRequest(bet_amount=30)))
    assert loss.status == BlackjackStatus.FINISHED
    assert loss.outcome == BlackjackOutcome.DEALER_BLACKJACK
    assert loss.payout == 0
    assert loss.new_balance == 470
    assert db_loss.state["credits"] == 470

    # Mutual BJ push: p1=A, d1=A, p2=K, d2=Q
    svc_push, db_push, _ = _make_service(
        credits=500,
        cards=[c(Rank.ACE), c(Rank.ACE), c(Rank.KING), c(Rank.QUEEN)],
    )
    push = asyncio.run(svc_push.start(make_user(), BlackjackStartRequest(bet_amount=30)))
    assert push.status == BlackjackStatus.FINISHED
    assert push.outcome == BlackjackOutcome.PUSH
    assert push.payout == 30
    assert push.net_profit == 0
    assert push.new_balance == 500
    assert db_push.state["credits"] == 500
    assert [doc["Reason"] for _id, doc in db_push.state["transactions"]] == [
        BlackjackService.BET_REASON,
        BlackjackService.PUSH_REASON,
    ]


def test_in_progress_hides_dealer_hole_card_and_allows_hit_stand_double() -> None:
    # Deal: p1=6, d1=10, p2=5, d2=9 (player=11, dealer=19 hidden)
    service, db, _ = _make_service(
        credits=500,
        cards=[c(Rank.SIX), c(Rank.TEN), c(Rank.FIVE), c(Rank.NINE), c(Rank.SEVEN)],
    )
    user = make_user()
    started = asyncio.run(service.start(user, BlackjackStartRequest(bet_amount=50)))

    assert started.status == BlackjackStatus.IN_PROGRESS
    assert started.outcome is None
    assert started.player_value == 11
    assert len(started.dealer_cards) == 1
    assert started.dealer_value == 10
    assert started.dealer_hidden_cards == 1
    assert started.available_actions == [
        BlackjackAction.HIT,
        BlackjackAction.STAND,
        BlackjackAction.DOUBLE,
    ]
    assert started.new_balance == 450
    assert db.state["credits"] == 450

    # Hit draws 7 -> player=18, double is no longer available.
    after_hit = asyncio.run(service.hit(user, started.game_id))
    assert after_hit.status == BlackjackStatus.IN_PROGRESS
    assert after_hit.player_value == 18
    assert after_hit.available_actions == [BlackjackAction.HIT, BlackjackAction.STAND]

    # Double is rejected after a hit.
    with pytest.raises(BlackjackInvalidActionError):
        asyncio.run(service.double_down(user, started.game_id))

    # Stand reveals dealer 19 > 18 -> dealer wins.
    after_stand = asyncio.run(service.stand(user, started.game_id))
    assert after_stand.status == BlackjackStatus.FINISHED
    assert after_stand.outcome == BlackjackOutcome.DEALER_WIN
    assert after_stand.dealer_hidden_cards == 0
    assert len(after_stand.dealer_cards) == 2
    assert after_stand.dealer_value == 19
    assert after_stand.payout == 0
    assert after_stand.new_balance == 450


def test_hit_to_21_auto_stands_and_bust_finishes_immediately() -> None:
    # Hit to 21: p1=6, d1=10, p2=5, d2=7, hit=10 -> auto-stand 21 vs 17 -> win!
    svc_win, db_win, _ = _make_service(
        credits=500,
        cards=[c(Rank.SIX), c(Rank.TEN), c(Rank.FIVE), c(Rank.SEVEN), c(Rank.TEN)],
    )
    user = make_user()
    g1 = asyncio.run(svc_win.start(user, BlackjackStartRequest(bet_amount=40)))
    r1 = asyncio.run(svc_win.hit(user, g1.game_id))
    assert r1.status == BlackjackStatus.FINISHED
    assert r1.outcome == BlackjackOutcome.PLAYER_WIN
    assert r1.player_value == 21
    assert r1.payout == 80
    assert r1.new_balance == 540
    assert db_win.state["credits"] == 540

    # Hit bust: p1=10, d1=9, p2=6, d2=8, hit=9 -> bust (25)
    svc_bust, db_bust, _ = _make_service(
        credits=500,
        cards=[c(Rank.TEN), c(Rank.NINE), c(Rank.SIX), c(Rank.EIGHT), c(Rank.NINE)],
    )
    g2 = asyncio.run(svc_bust.start(user, BlackjackStartRequest(bet_amount=40)))
    r2 = asyncio.run(svc_bust.hit(user, g2.game_id))
    assert r2.status == BlackjackStatus.FINISHED
    assert r2.outcome == BlackjackOutcome.PLAYER_BUST
    assert r2.player_value == 25
    assert r2.payout == 0
    assert r2.new_balance == 460
    assert len(r2.dealer_cards) == 2
    assert db_bust.state["credits"] == 460


def test_double_down_win_bust_and_insufficient_credits_keeps_round_alive() -> None:
    # Double win: p1=6, d1=10, p2=5, d2=6 (dealer=16), double=10 (player=21), dealer draws 10 -> dealer bust!
    svc_win, db_win, _ = _make_service(
        credits=500,
        cards=[
            c(Rank.SIX),
            c(Rank.TEN),
            c(Rank.FIVE),
            c(Rank.SIX),
            c(Rank.TEN),
            c(Rank.TEN),
        ],
    )
    user = make_user()
    started = asyncio.run(svc_win.start(user, BlackjackStartRequest(bet_amount=50)))
    doubled = asyncio.run(svc_win.double_down(user, started.game_id))

    assert doubled.status == BlackjackStatus.FINISHED
    assert doubled.outcome == BlackjackOutcome.DEALER_BUST
    assert doubled.bet_amount == 100
    assert doubled.payout == 200
    assert doubled.net_profit == 100
    assert doubled.new_balance == 600
    assert db_win.state["credits"] == 600
    assert [doc["Reason"] for _id, doc in db_win.state["transactions"]] == [
        BlackjackService.BET_REASON,
        BlackjackService.DOUBLE_REASON,
        BlackjackService.WIN_REASON,
    ]

    # Insufficient credits for double leaves game IN_PROGRESS so player can still stand!
    svc_short, db_short, _ = _make_service(
        credits=60,
        cards=[c(Rank.TEN), c(Rank.TEN), c(Rank.NINE), c(Rank.SEVEN), c(Rank.FIVE)],
    )
    g2 = asyncio.run(svc_short.start(user, BlackjackStartRequest(bet_amount=50)))
    assert db_short.state["credits"] == 10

    with pytest.raises(InsufficientCreditsError):
        asyncio.run(svc_short.double_down(user, g2.game_id))

    resumed = asyncio.run(svc_short.stand(user, g2.game_id))
    assert resumed.status == BlackjackStatus.FINISHED
    assert resumed.outcome == BlackjackOutcome.PLAYER_WIN
    assert resumed.bet_amount == 50
    assert resumed.payout == 100
    assert resumed.new_balance == 110


def test_session_ownership_ttl_active_limit_and_concurrent_stand_lock() -> None:
    clock = MutableClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    # Deal: p1=10, d1=9, p2=8 (player=18), d2=6 (dealer=15), dealer draws 2 -> 17 < 18 (win)
    service, db, _ = _make_service(
        credits=500,
        cards=[c(Rank.TEN), c(Rank.NINE), c(Rank.EIGHT), c(Rank.SIX), c(Rank.TWO)],
        clock=clock,
    )
    owner = make_user("owner")
    other = make_user("other")

    with pytest.raises(BetLimitExceededError):
        asyncio.run(service.start(owner, BlackjackStartRequest(bet_amount=4)))
    with pytest.raises(BetLimitExceededError):
        asyncio.run(service.start(owner, BlackjackStartRequest(bet_amount=201)))

    game = asyncio.run(service.start(owner, BlackjackStartRequest(bet_amount=50)))

    # Active game limit blocks second simultaneous start for owner, not for other user.
    with pytest.raises(BlackjackActiveGameExistsError):
        asyncio.run(service.start(owner, BlackjackStartRequest(bet_amount=50)))

    # Foreign user gets 404.
    with pytest.raises(BlackjackGameNotFoundError):
        asyncio.run(service.get_game(other, game.game_id))
    with pytest.raises(BlackjackGameNotFoundError):
        asyncio.run(service.stand(other, game.game_id))

    # Concurrent stand calls: lock guarantees only one resolves and pays out.
    async def race_stand() -> list[object]:
        return await asyncio.gather(
            service.stand(owner, game.game_id),
            service.stand(owner, game.game_id),
            return_exceptions=True,
        )

    outcomes = asyncio.run(race_stand())
    successes = [item for item in outcomes if not isinstance(item, Exception)]
    conflicts = [item for item in outcomes if isinstance(item, BlackjackInvalidActionError)]
    assert len(successes) == 1
    assert len(conflicts) == 1
    assert db.state["credits"] == 550  # Paid out once, never twice.

    # Once finished, starting a new game is allowed again.
    g2 = asyncio.run(service.start(owner, BlackjackStartRequest(bet_amount=20)))
    clock.advance(1801)
    with pytest.raises(BlackjackGameNotFoundError):
        asyncio.run(service.get_game(owner, g2.game_id))
