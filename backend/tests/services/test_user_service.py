from google.api_core.exceptions import Aborted, PermissionDenied, RetryError
from google.auth.exceptions import GoogleAuthError
from google.cloud.firestore import SERVER_TIMESTAMP
import pytest

from src.services.user_service import UserService
from src.utils.exceptions import (
    AuthenticationError,
    InsufficientCreditsError,
    ProfileAlreadyExistsError,
    ProfileUnavailableError,
)
from tests.fakes.auth import DEFAULT_UID, make_user
from tests.fakes.firestore import FakeFirestoreDB


# --- add_credits & remove_credits ---


def test_add_credits_updates_balance_and_logs_transaction_atomically() -> None:
    db = FakeFirestoreDB(credits=100)
    service = UserService(db)  # type: ignore[arg-type]

    service.add_credits(make_user(), 25, "Ocena fiszki")

    assert db.seen_uids == [DEFAULT_UID]
    assert db.state["credits"] == 125.0
    assert len(db.transactions) == 1
    assert db.transactions[0].committed is True
    assert db.transactions[0].rolled_back is False
    assert db.user_doc.seen_transactions == [db.transactions[0]]
    assert db.state["transactions"] == [
        ("tx-1", {"value": 25.0, "Reason": "Ocena fiszki", "timestamp": SERVER_TIMESTAMP})
    ]


def test_remove_credits_subtracts_balance_and_logs_negative_transaction() -> None:
    db = FakeFirestoreDB(credits=100)
    service = UserService(db)  # type: ignore[arg-type]

    service.remove_credits(make_user(), 30, "Wykorzystanie gry")

    assert db.state["credits"] == 70.0
    assert db.transactions[0].committed is True
    assert db.state["transactions"] == [
        ("tx-1", {"value": -30.0, "Reason": "Wykorzystanie gry", "timestamp": SERVER_TIMESTAMP})
    ]


def test_sequential_add_and_remove_credits_accumulate_distinct_transactions() -> None:
    db = FakeFirestoreDB(credits=50)
    service = UserService(db)  # type: ignore[arg-type]
    user = make_user()

    service.add_credits(user, 10.5, "Bonus 1")
    service.remove_credits(user, 5.5, "Opłata")
    service.add_credits(user, 20, "Bonus 2")

    assert db.state["credits"] == 75.0
    assert db.state["transactions"] == [
        ("tx-1", {"value": 10.5, "Reason": "Bonus 1", "timestamp": SERVER_TIMESTAMP}),
        ("tx-2", {"value": -5.5, "Reason": "Opłata", "timestamp": SERVER_TIMESTAMP}),
        ("tx-3", {"value": 20.0, "Reason": "Bonus 2", "timestamp": SERVER_TIMESTAMP}),
    ]


@pytest.mark.parametrize(
    "bad_amount",
    [0, -1, -0.5, True, False, float("nan"), float("inf"), float("-inf"), "10"],
)
def test_add_and_remove_credits_reject_invalid_amounts_before_firestore(
    bad_amount: object,
) -> None:
    db = FakeFirestoreDB(credits=100)
    service = UserService(db)  # type: ignore[arg-type]
    user = make_user()

    with pytest.raises(ValueError):
        service.add_credits(user, bad_amount, "Bad add")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        service.remove_credits(user, bad_amount, "Bad remove")  # type: ignore[arg-type]

    assert db.seen_uids == []
    assert db.transactions == []


@pytest.mark.parametrize("bad_uid", ["a/b", ".", ".."])
def test_credit_and_transaction_methods_reject_unsafe_uids(bad_uid: str) -> None:
    db = FakeFirestoreDB(credits=100)
    service = UserService(db)  # type: ignore[arg-type]
    user = make_user(bad_uid)

    with pytest.raises(AuthenticationError):
        service.add_credits(user, 10, "reason")
    with pytest.raises(AuthenticationError):
        service.remove_credits(user, 10, "reason")
    with pytest.raises(AuthenticationError):
        service.get_credits(user)
    with pytest.raises(AuthenticationError):
        service.record_transaction(bad_uid, 10, "reason")
    with pytest.raises(AuthenticationError):
        service.settle_game_wager(user, 10, 0, "bet", "win")

    assert db.seen_uids == []


# --- get_credits & record_transaction ---


def test_get_credits_handles_existing_missing_and_default_profile() -> None:
    assert UserService(FakeFirestoreDB(credits=340)).get_credits(make_user()) == 340  # type: ignore[arg-type]
    assert UserService(FakeFirestoreDB(exists=False)).get_credits(make_user()) == 0  # type: ignore[arg-type]
    assert (
        UserService(FakeFirestoreDB(include_credits_field=False)).get_credits(make_user()) == 0  # type: ignore[arg-type]
    )


def test_record_transaction_writes_expected_schema() -> None:
    db = FakeFirestoreDB()
    service = UserService(db)  # type: ignore[arg-type]

    service.record_transaction(DEFAULT_UID, -12.5, "Manual adjustment")

    assert db.seen_uids == [DEFAULT_UID]
    assert db.state["direct_transactions"] == [
        ("tx-1", {"value": -12.5, "Reason": "Manual adjustment", "timestamp": SERVER_TIMESTAMP})
    ]


# --- get_current_user & register_user ---


def test_get_current_user_reads_profile_and_raises_when_missing() -> None:
    db = FakeFirestoreDB(credits=42)
    result = UserService(db).get_current_user(make_user())  # type: ignore[arg-type]

    assert result.uid == DEFAULT_UID
    assert result.profile.credits == 42

    missing_db = FakeFirestoreDB(exists=False)
    with pytest.raises(ProfileUnavailableError):
        UserService(missing_db).get_current_user(make_user())  # type: ignore[arg-type]


def test_register_user_creates_profile_once_and_rejects_duplicates() -> None:
    db = FakeFirestoreDB(exists=False)
    created = UserService(db).register_user(make_user())  # type: ignore[arg-type]

    assert created.uid == DEFAULT_UID
    assert created.profile.credits == 0
    assert db.user_doc.create_calls == [{"created_at": SERVER_TIMESTAMP, "credits": 0}]

    with pytest.raises(ProfileAlreadyExistsError):
        UserService(db).register_user(make_user())  # type: ignore[arg-type]


# --- settle_game_wager ---


def test_settle_game_wager_unit_validation_guards() -> None:
    db = FakeFirestoreDB(credits=100)
    service = UserService(db)  # type: ignore[arg-type]
    user = make_user("user-1")

    with pytest.raises(ValueError):
        service.settle_game_wager(user, 0, 0, "bet", "win")
    with pytest.raises(ValueError):
        service.settle_game_wager(user, True, 0, "bet", "win")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        service.settle_game_wager(user, 10, -1, "bet", "win")
    with pytest.raises(ValueError):
        service.settle_game_wager(user, 10, False, "bet", "win")  # type: ignore[arg-type]

    db_missing = FakeFirestoreDB(credits=100, exists=False)
    with pytest.raises(ProfileUnavailableError):
        UserService(db_missing).settle_game_wager(user, 10, 0, "bet", "win")  # type: ignore[arg-type]

    with pytest.raises(InsufficientCreditsError):
        service.settle_game_wager(user, 200, 0, "bet", "win")


def test_settle_game_wager_winning_spin_logs_bet_and_win_and_returns_int_balance() -> None:
    db = FakeFirestoreDB(credits=500)
    service = UserService(db)  # type: ignore[arg-type]

    new_balance = service.settle_game_wager(
        make_user(), bet=25, payout=90, bet_reason="Ruleta: zakład", win_reason="Ruleta: wygrana"
    )

    assert new_balance == 565
    assert isinstance(db.state["credits"], int)
    assert db.state["credits"] == 565
    assert db.transactions[0].committed is True
    assert db.state["transactions"] == [
        ("tx-1", {"value": -25.0, "Reason": "Ruleta: zakład", "timestamp": SERVER_TIMESTAMP}),
        ("tx-2", {"value": 90.0, "Reason": "Ruleta: wygrana", "timestamp": SERVER_TIMESTAMP}),
    ]


def test_settle_game_wager_losing_spin_logs_only_bet() -> None:
    db = FakeFirestoreDB(credits=500)
    service = UserService(db)  # type: ignore[arg-type]

    new_balance = service.settle_game_wager(
        make_user(), bet=50, payout=0, bet_reason="Ruleta: zakład", win_reason="Ruleta: wygrana"
    )

    assert new_balance == 450
    assert db.state["credits"] == 450
    assert db.state["transactions"] == [
        ("tx-1", {"value": -50.0, "Reason": "Ruleta: zakład", "timestamp": SERVER_TIMESTAMP})
    ]


def test_settle_game_wager_exact_balance_and_break_even_edges() -> None:
    all_in_db = FakeFirestoreDB(credits=100)
    assert (
        UserService(all_in_db).settle_game_wager(  # type: ignore[arg-type]
            make_user(), bet=100, payout=0, bet_reason="bet", win_reason="win"
        )
        == 0
    )
    assert all_in_db.state["credits"] == 0

    even_db = FakeFirestoreDB(credits=100)
    assert (
        UserService(even_db).settle_game_wager(  # type: ignore[arg-type]
            make_user(), bet=40, payout=40, bet_reason="bet", win_reason="win"
        )
        == 100
    )
    assert even_db.state["credits"] == 100
    assert [doc["value"] for _id, doc in even_db.state["transactions"]] == [-40.0, 40.0]


def test_settle_game_wager_insufficient_credits_rolls_back_without_writes() -> None:
    db = FakeFirestoreDB(credits=49)
    service = UserService(db)  # type: ignore[arg-type]

    with pytest.raises(InsufficientCreditsError):
        service.settle_game_wager(
            make_user(), bet=50, payout=100, bet_reason="bet", win_reason="win"
        )

    assert db.state["credits"] == 49
    assert db.state["transactions"] == []
    assert db.transactions[0].committed is False
    assert db.transactions[0].rolled_back is True


def test_settle_game_wager_missing_profile_raises_503_and_rolls_back() -> None:
    db = FakeFirestoreDB(exists=False)
    service = UserService(db)  # type: ignore[arg-type]

    with pytest.raises(ProfileUnavailableError):
        service.settle_game_wager(
            make_user(), bet=10, payout=0, bet_reason="bet", win_reason="win"
        )

    assert db.state["transactions"] == []
    assert db.transactions[0].rolled_back is True


def test_settle_game_wager_retries_on_aborted_contention_without_duplicate_transactions() -> None:
    def concurrent_deduction(attempt: int, state: dict[str, object]) -> None:
        if attempt == 1:
            # Another concurrent request reduced credits from 500 -> 450 before retry.
            state["credits"] = 450

    db = FakeFirestoreDB(
        credits=500,
        commit_errors=[Aborted("concurrent write")],
        on_retry=concurrent_deduction,
    )
    service = UserService(db)  # type: ignore[arg-type]

    new_balance = service.settle_game_wager(
        make_user(), bet=20, payout=40, bet_reason="bet", win_reason="win"
    )

    assert db.transactions[0].attempts == 2
    assert db.transactions[0].committed is True
    assert new_balance == 470
    assert db.state["credits"] == 470
    # Only the committed attempt's two transaction docs exist, with fresh IDs.
    assert db.state["transactions"] == [
        ("tx-3", {"value": -20.0, "Reason": "bet", "timestamp": SERVER_TIMESTAMP}),
        ("tx-4", {"value": 40.0, "Reason": "win", "timestamp": SERVER_TIMESTAMP}),
    ]


def test_settle_game_wager_aborted_retry_prevents_double_spend() -> None:
    def concurrent_spend(attempt: int, state: dict[str, object]) -> None:
        if attempt == 1:
            # Concurrent spin spent 50 of 100 credits, leaving 50 < bet (80).
            state["credits"] = 50

    db = FakeFirestoreDB(
        credits=100,
        commit_errors=[Aborted("concurrent write")],
        on_retry=concurrent_spend,
    )
    service = UserService(db)  # type: ignore[arg-type]

    with pytest.raises(InsufficientCreditsError):
        service.settle_game_wager(
            make_user(), bet=80, payout=160, bet_reason="bet", win_reason="win"
        )

    assert db.transactions[0].attempts == 2
    assert db.transactions[0].committed is False
    assert db.transactions[0].rolled_back is True
    assert db.state["credits"] == 50
    assert db.state["transactions"] == []


@pytest.mark.parametrize(
    "error",
    [
        PermissionDenied("firestore permission denied"),
        RetryError("deadline exceeded", cause=RuntimeError("timeout")),
        GoogleAuthError("invalid service credentials"),
    ],
)
def test_settle_game_wager_maps_firestore_errors_to_profile_unavailable(
    error: Exception,
) -> None:
    db = FakeFirestoreDB(credits=500, get_error=error)
    service = UserService(db)  # type: ignore[arg-type]

    with pytest.raises(ProfileUnavailableError):
        service.settle_game_wager(
            make_user(), bet=10, payout=0, bet_reason="bet", win_reason="win"
        )

    assert db.transactions[0].rolled_back is True
