from collections.abc import Iterator
from fractions import Fraction
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from google.api_core.exceptions import PermissionDenied as FirestorePermissionDenied
from google.cloud.firestore import SERVER_TIMESTAMP
from pydantic import ValidationError

from src.configs.games.ruleta import RuletaSettings
from src.dependencies import get_ruleta_service
from src.main import create_app
from src.models.auth import AuthenticatedUser
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
from src.services.games.ruleta_service import RuletaService
from src.services.user_service import UserService
from src.utils.exceptions import InsufficientCreditsError, ProfileUnavailableError

AUTH = {"Authorization": "Bearer test-token"}


class FakeTransaction:
    """In-memory Transaction compatible with google.cloud.firestore.transactional."""

    def __init__(self, state: dict[str, object]) -> None:
        self._state = state
        self._max_attempts = 5
        self._read_only = False
        self._id = b"fake-tx-id"
        self.updates: list[tuple[object, dict[str, object]]] = []
        self.creates: list[tuple[object, dict[str, object]]] = []
        self.committed = False
        self.rolled_back = False

    def _clean_up(self) -> None:
        self.updates.clear()
        self.creates.clear()

    def _begin(self, retry_id: object = None) -> None:
        return None

    def update(self, reference: object, fields: dict[str, object]) -> None:
        self.updates.append((reference, dict(fields)))

    def create(self, reference: object, data: dict[str, object]) -> None:
        self.creates.append((reference, dict(data)))

    def _commit(self) -> None:
        for _ref, fields in self.updates:
            self._state["credits"] = fields["credits"]
        for ref, data in self.creates:
            self._state["transactions"].append((ref, data))
        self.committed = True

    def _rollback(self) -> None:
        self.updates.clear()
        self.creates.clear()
        self.rolled_back = True


class FakeUserDocument:
    def __init__(self, state: dict[str, object]) -> None:
        self._state = state
        self._transactions_collection = Mock()
        self._transactions_collection.document.side_effect = (
            lambda: f"tx-{len(self._state['transactions']) + len(self._state['created_refs'])}"
        )

    def get(self, transaction: FakeTransaction | None = None) -> Mock:
        error = self._state.get("get_error")
        if error is not None:
            raise error
        snapshot = Mock(exists=self._state["exists"])
        snapshot.to_dict.return_value = {"credits": self._state["credits"]}
        return snapshot

    def collection(self, name: str) -> Mock:
        assert name == "transactions"
        ref_factory = Mock()

        def make_ref() -> str:
            ref = f"tx-ref-{len(self._state['created_refs'])}"
            self._state["created_refs"].append(ref)
            return ref

        ref_factory.document.side_effect = make_ref
        return ref_factory


class FakeFirestoreDB:
    def __init__(self, credits: int = 500, exists: bool = True) -> None:
        self.state: dict[str, object] = {
            "credits": credits,
            "exists": exists,
            "transactions": [],
            "created_refs": [],
            "get_error": None,
        }
        self.seen_uids: list[str] = []
        self.last_transaction: FakeTransaction | None = None
        self._user_doc = FakeUserDocument(self.state)

    def collection(self, name: str) -> Mock:
        assert name == "users"
        users_col = Mock()

        def get_doc(uid: str) -> FakeUserDocument:
            self.seen_uids.append(uid)
            return self._user_doc

        users_col.document.side_effect = get_doc
        return users_col

    def transaction(self) -> FakeTransaction:
        tx = FakeTransaction(self.state)
        self.last_transaction = tx
        return tx


@pytest.fixture
def verify_token(monkeypatch: pytest.MonkeyPatch) -> Mock:
    monkeypatch.setattr("src.main.init_firebase", lambda settings: False)
    monkeypatch.setattr("src.services.auth_service.is_firebase_initialized", lambda: True)
    verify = Mock(
        return_value={
            "uid": "firebase-user-123",
            "email": "learner@example.test",
            "email_verified": True,
            "name": "Learner",
            "exp": 9999999999,
            "firebase": {"sign_in_provider": "password"},
        }
    )
    monkeypatch.setattr("src.services.auth_service.auth.verify_id_token", verify)
    return verify


@pytest.fixture
def ruleta_harness(
    verify_token: Mock,
) -> Iterator[callable]:
    clients: list[TestClient] = []

    def open_client(
        credits: int = 500,
        exists: bool = True,
        winning_number: int = 7,
        settings: RuletaSettings | None = None,
    ) -> tuple[TestClient, FakeFirestoreDB]:
        db = FakeFirestoreDB(credits=credits, exists=exists)
        app = create_app()
        app.dependency_overrides[get_ruleta_service] = lambda: RuletaService(
            user_service=UserService(db),
            settings=settings or RuletaSettings(_env_file=None),
            rng=lambda: winning_number,
        )
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client, db

    yield open_client

    for client in clients:
        client.__exit__(None, None, None)


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


# --- 4. Request schema, configurable limits & anti-tampering ---


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"bets": []},
        {"bets": [{"bet_type": "red", "amount": 1}] * 21},
        {"bets": [{"bet_type": "red", "amount": 0}]},
        {"bets": [{"bet_type": "red", "amount": -5}]},
        {"bets": [{"bet_type": "red", "amount": 1001}]},
        {"bets": [{"bet_type": "red", "amount": True}]},
        {"bets": [{"bet_type": "red", "amount": 10.5}]},
        {"bets": [{"bet_type": "red", "amount": 1000}] * 6},  # > default max_total_bet (5000)
        {"bets": [{"bet_type": "red", "amount": 10, "payout": 9999}]},
        {"bets": [{"bet_type": "red", "amount": 10}], "winning_number": 7},
        {"bets": [{"bet_type": "red", "amount": 10}], "uid": "victim"},
        {"bets": [{"bet_type": "split", "amount": 10, "numbers": [3, 4]}]},
    ],
)
def test_spin_endpoint_rejects_tampered_or_invalid_payloads(
    ruleta_harness: callable, payload: dict
) -> None:
    client, db = ruleta_harness(credits=10000)

    response = client.post("/api/games/ruleta/spin", json=payload, headers=AUTH)

    assert response.status_code == 422
    assert db.seen_uids == []


def test_total_bet_exact_limit_is_accepted(ruleta_harness: callable) -> None:
    client, db = ruleta_harness(credits=10000, winning_number=7)

    response = client.post(
        "/api/games/ruleta/spin",
        json={"bets": [{"bet_type": "red", "amount": 1000}] * 5},
        headers=AUTH,
    )

    assert response.status_code == 200
    assert response.json()["total_bet"] == 5000
    assert db.state["credits"] == 15000


def test_ruleta_settings_reads_env_and_validates_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RULETA_MIN_BET_AMOUNT", "5")
    monkeypatch.setenv("RULETA_MAX_BET_AMOUNT", "250")
    monkeypatch.setenv("RULETA_MAX_TOTAL_BET", "1000")
    monkeypatch.setenv("RULETA_MAX_BETS_PER_SPIN", "8")

    settings = RuletaSettings(_env_file=None)
    assert settings.min_bet_amount == 5
    assert settings.max_bet_amount == 250
    assert settings.max_total_bet == 1000
    assert settings.max_bets_per_spin == 8

    with pytest.raises(ValidationError):
        RuletaSettings(_env_file=None, min_bet_amount=0)
    with pytest.raises(ValidationError):
        RuletaSettings(_env_file=None, min_bet_amount=100, max_bet_amount=50)
    with pytest.raises(ValidationError):
        RuletaSettings(_env_file=None, max_bet_amount=600, max_total_bet=500)


@pytest.mark.parametrize(
    ("bets", "expected_detail"),
    [
        ([{"bet_type": "red", "amount": 4}], "Bet amount must be at least 5"),
        ([{"bet_type": "red", "amount": 51}], "Bet amount cannot exceed 50"),
        (
            [{"bet_type": "red", "amount": 45}, {"bet_type": "black", "amount": 40}],
            "Total bet 85 exceeds maximum allowed (80)",
        ),
        (
            [
                {"bet_type": "red", "amount": 10},
                {"bet_type": "even", "amount": 10},
                {"bet_type": "low", "amount": 10},
            ],
            "Number of bets exceeds maximum allowed (2)",
        ),
    ],
)
def test_custom_ruleta_settings_enforce_table_limits_before_firestore(
    ruleta_harness: callable, bets: list[dict], expected_detail: str
) -> None:
    custom = RuletaSettings(
        _env_file=None,
        min_bet_amount=5,
        max_bet_amount=50,
        max_total_bet=80,
        max_bets_per_spin=2,
    )
    client, db = ruleta_harness(credits=500, winning_number=7, settings=custom)

    rejected = client.post("/api/games/ruleta/spin", json={"bets": bets}, headers=AUTH)

    assert rejected.status_code == 422
    assert rejected.json() == {"detail": expected_detail}
    assert db.seen_uids == []

    allowed = client.post(
        "/api/games/ruleta/spin",
        json={
            "bets": [
                {"bet_type": "red", "amount": 50},
                {"bet_type": "odd", "amount": 30},
            ]
        },
        headers=AUTH,
    )
    assert allowed.status_code == 200
    assert allowed.json()["total_bet"] == 80


# --- 5. Auth & HTTP security ---


@pytest.mark.parametrize("authorization", [None, "", "Basic abc", "Bearer", "Bearer "])
def test_spin_requires_bearer_token(
    ruleta_harness: callable, verify_token: Mock, authorization: str | None
) -> None:
    client, db = ruleta_harness()
    headers = {"Authorization": authorization} if authorization is not None else {}

    response = client.post(
        "/api/games/ruleta/spin",
        json={"bets": [{"bet_type": "red", "amount": 10}]},
        headers=headers,
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    verify_token.assert_not_called()
    assert db.seen_uids == []


def test_spin_rejects_unverified_email(
    ruleta_harness: callable, verify_token: Mock
) -> None:
    verify_token.return_value["email_verified"] = False
    client, db = ruleta_harness()

    response = client.post(
        "/api/games/ruleta/spin",
        json={"bets": [{"bet_type": "red", "amount": 10}]},
        headers=AUTH,
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Email verification required"}
    assert db.seen_uids == []


def test_spin_openapi_declares_bearer_authentication(ruleta_harness: callable) -> None:
    client, _db = ruleta_harness()
    schema = client.get("/openapi.json").json()

    assert schema["paths"]["/api/games/ruleta/spin"]["post"]["security"] == [{"HTTPBearer": []}]
    assert "/api/games/ruleta/rules" not in schema["paths"]


# --- 6. Atomic Firestore settlement & edge cases ---


def test_winning_spin_settles_credits_and_logs_both_transactions(
    ruleta_harness: callable,
) -> None:
    # 7 is red
    client, db = ruleta_harness(credits=500, winning_number=7)

    response = client.post(
        "/api/games/ruleta/spin",
        json={"bets": [{"bet_type": "straight", "numbers": [7], "amount": 10}]},
        headers=AUTH,
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "winning_number": 7,
        "color": "red",
        "total_bet": 10,
        "total_payout": 360,
        "net_profit": 350,
        "new_balance": 850,
        "bets": [
            {
                "bet_type": "straight",
                "numbers": [7],
                "selection": None,
                "amount": 10,
                "won": True,
                "payout": 360,
            }
        ],
    }
    assert db.seen_uids == ["firebase-user-123"]
    assert db.state["credits"] == 850
    assert db.last_transaction is not None
    assert db.last_transaction.committed is True
    assert db.last_transaction.rolled_back is False
    tx_docs = [data for _ref, data in db.state["transactions"]]
    assert tx_docs == [
        {"value": -10.0, "Reason": RuletaService.BET_REASON, "timestamp": SERVER_TIMESTAMP},
        {"value": 360.0, "Reason": RuletaService.WIN_REASON, "timestamp": SERVER_TIMESTAMP},
    ]


def test_losing_spin_deducts_bet_and_logs_only_wager_transaction(
    ruleta_harness: callable,
) -> None:
    # 15 is black
    client, db = ruleta_harness(credits=500, winning_number=15)

    response = client.post(
        "/api/games/ruleta/spin",
        json={"bets": [{"bet_type": "red", "amount": 25}]},
        headers=AUTH,
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "winning_number": 15,
        "color": "black",
        "total_bet": 25,
        "total_payout": 0,
        "net_profit": -25,
        "new_balance": 475,
        "bets": [
            {
                "bet_type": "red",
                "numbers": None,
                "selection": None,
                "amount": 25,
                "won": False,
                "payout": 0,
            }
        ],
    }
    assert db.state["credits"] == 475
    tx_docs = [data for _ref, data in db.state["transactions"]]
    assert tx_docs == [
        {"value": -25.0, "Reason": RuletaService.BET_REASON, "timestamp": SERVER_TIMESTAMP},
    ]


def test_multi_bet_break_even_spin_preserves_audit_trail(
    ruleta_harness: callable,
) -> None:
    # 2 is black, even, low (1-18). Bet 25 on red (loses) + 25 on black (wins 50) -> net 0.
    client, db = ruleta_harness(credits=500, winning_number=2)

    response = client.post(
        "/api/games/ruleta/spin",
        json={
            "bets": [
                {"bet_type": "red", "amount": 25},
                {"bet_type": "black", "amount": 25},
            ]
        },
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["winning_number"] == 2
    assert body["color"] == "black"
    assert body["total_bet"] == 50
    assert body["total_payout"] == 50
    assert body["net_profit"] == 0
    assert body["new_balance"] == 500
    assert body["bets"][0]["won"] is False
    assert body["bets"][1]["won"] is True
    assert db.state["credits"] == 500
    tx_docs = [data for _ref, data in db.state["transactions"]]
    assert [doc["value"] for doc in tx_docs] == [-50.0, 50.0]


def test_insufficient_credits_returns_400_and_never_mutates_or_leaks_outcome(
    ruleta_harness: callable,
) -> None:
    client, db = ruleta_harness(credits=40, winning_number=7)

    response = client.post(
        "/api/games/ruleta/spin",
        json={
            "bets": [
                {"bet_type": "red", "amount": 25},
                {"bet_type": "straight", "numbers": [7], "amount": 25},
            ]
        },
        headers=AUTH,
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Insufficient credits"}
    assert "winning_number" not in response.text
    assert db.state["credits"] == 40
    assert db.state["transactions"] == []
    assert db.last_transaction is not None
    assert db.last_transaction.committed is False
    assert db.last_transaction.rolled_back is True


def test_missing_profile_returns_503_and_does_not_leak_spin(
    ruleta_harness: callable,
) -> None:
    client, db = ruleta_harness(credits=500, exists=False, winning_number=7)

    response = client.post(
        "/api/games/ruleta/spin",
        json={"bets": [{"bet_type": "red", "amount": 10}]},
        headers=AUTH,
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "User profile service unavailable"}
    assert "winning_number" not in response.text
    assert db.state["transactions"] == []


def test_firestore_error_returns_generic_503(
    ruleta_harness: callable,
) -> None:
    client, db = ruleta_harness(credits=500, winning_number=7)
    db.state["get_error"] = FirestorePermissionDenied("private project configuration")

    response = client.post(
        "/api/games/ruleta/spin",
        json={"bets": [{"bet_type": "red", "amount": 10}]},
        headers=AUTH,
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "User profile service unavailable"}
    assert "private project configuration" not in response.text


@pytest.mark.parametrize("uid", ["x/private/y", ".", ".."])
def test_unsafe_uid_is_rejected_before_touching_firestore(
    ruleta_harness: callable, verify_token: Mock, uid: str
) -> None:
    verify_token.return_value["uid"] = uid
    client, db = ruleta_harness(credits=500)

    response = client.post(
        "/api/games/ruleta/spin",
        json={"bets": [{"bet_type": "red", "amount": 10}]},
        headers=AUTH,
    )

    assert response.status_code == 401
    assert db.seen_uids == []


def test_settle_game_wager_unit_validation_guards() -> None:
    db = FakeFirestoreDB(credits=100)
    service = UserService(db)
    user = AuthenticatedUser(uid="user-1", email_verified=True)

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
        UserService(db_missing).settle_game_wager(user, 10, 0, "bet", "win")

    with pytest.raises(InsufficientCreditsError):
        service.settle_game_wager(user, 200, 0, "bet", "win")
