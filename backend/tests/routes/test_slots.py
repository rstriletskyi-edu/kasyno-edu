from collections.abc import Callable
from unittest.mock import Mock

from fastapi.testclient import TestClient
from google.api_core.exceptions import PermissionDenied as FirestorePermissionDenied
from google.cloud.firestore import SERVER_TIMESTAMP
import pytest

from src.configs.games.slots import SlotsSettings, get_slots_settings
from src.dependencies import get_slots_service
from src.services.games.slots_service import SlotsService
from src.services.user_service import UserService
from tests.fakes.auth import AUTH_HEADERS, DEFAULT_UID, INVALID_AUTH_HEADERS, UNSAFE_UIDS
from tests.fakes.firestore import FakeFirestoreDB


@pytest.fixture
def slots_client(
    make_client: Callable[..., TestClient],
    make_firestore_db: Callable[..., FakeFirestoreDB],
    verify_token: Mock,
) -> Callable[..., tuple[TestClient, FakeFirestoreDB]]:
    def _open(
        credits: int = 500,
        exists: bool = True,
        rolls: list[int] | None = None,
        settings: SlotsSettings | None = None,
        get_error: Exception | None = None,
    ) -> tuple[TestClient, FakeFirestoreDB]:
        db = make_firestore_db(credits=credits, exists=exists, get_error=get_error)
        resolved_settings = settings or SlotsSettings(_env_file=None)
        roll_iter = iter(rolls) if rolls is not None else None

        def next_roll(_bound: int) -> int:
            if roll_iter is None:
                return 0
            return next(roll_iter)

        service = SlotsService(
            user_service=UserService(db),
            settings=resolved_settings,
            rng=next_roll,
        )
        client = make_client(
            dependency_overrides={
                get_slots_service: lambda: service,
                get_slots_settings: lambda: resolved_settings,
            }
        )
        return client, db

    return _open


# --- GET /api/games/slots/config ---


def test_config_endpoint_is_public_and_hides_rtp_by_default(
    make_client: Callable[..., TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.auth_service.is_firebase_initialized", lambda: False)
    settings = SlotsSettings(_env_file=None, expose_rtp=False)
    client = make_client(dependency_overrides={get_slots_settings: lambda: settings})

    response = client.get("/api/games/slots/config")

    assert response.status_code == 200
    body = response.json()
    assert body["reels"] == 3
    assert body["rows"] == 1
    assert body["min_bet_amount"] == 1
    assert body["max_bet_amount"] == 500
    assert body["rtp"] is None
    assert len(body["symbols"]) == 6
    assert all(symbol["probability"] is None for symbol in body["symbols"])
    assert "weight" not in response.text
    assert len(body["paytable"]) == 7


def test_config_endpoint_exposes_rtp_and_probabilities_when_enabled(
    slots_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    client, _db = slots_client(settings=SlotsSettings(_env_file=None, expose_rtp=True))

    response = client.get("/api/games/slots/config")

    assert response.status_code == 200
    body = response.json()
    assert body["rtp"] == 0.95256
    assert [symbol["id"] for symbol in body["symbols"]] == [
        "cherry",
        "lemon",
        "orange",
        "bell",
        "star",
        "seven",
    ]
    assert round(sum(symbol["probability"] for symbol in body["symbols"]), 6) == 1.0
    assert "weight" not in response.text


# --- POST /api/games/slots/spin validation & auth ---


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"bet_amount": 0},
        {"bet_amount": -5},
        {"bet_amount": 501},
        {"bet_amount": True},
        {"bet_amount": 10.5},
        {"bet_amount": "10"},
        {"bet_amount": 10, "payout": 9999},
        {"bet_amount": 10, "reels": ["seven", "seven", "seven"]},
        {"bet_amount": 10, "uid": "victim"},
    ],
)
def test_spin_endpoint_rejects_tampered_or_invalid_payloads(
    slots_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    payload: dict[str, object],
) -> None:
    client, db = slots_client(credits=10000)

    response = client.post("/api/games/slots/spin", json=payload, headers=AUTH_HEADERS)

    assert response.status_code == 422
    assert db.seen_uids == []


@pytest.mark.parametrize(
    ("bet_amount", "expected_detail"),
    [
        (4, "Bet amount must be at least 5"),
        (51, "Bet amount cannot exceed 50"),
    ],
)
def test_custom_slots_settings_enforce_bet_limits_before_firestore(
    slots_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    bet_amount: int,
    expected_detail: str,
) -> None:
    custom = SlotsSettings(_env_file=None, min_bet_amount=5, max_bet_amount=50)
    client, db = slots_client(credits=500, rolls=[0, 0, 0], settings=custom)

    rejected = client.post(
        "/api/games/slots/spin",
        json={"bet_amount": bet_amount},
        headers=AUTH_HEADERS,
    )

    assert rejected.status_code == 422
    assert rejected.json() == {"detail": expected_detail}
    assert db.seen_uids == []

    allowed = client.post(
        "/api/games/slots/spin",
        json={"bet_amount": 50},
        headers=AUTH_HEADERS,
    )
    assert allowed.status_code == 200
    assert allowed.json()["bet_amount"] == 50


@pytest.mark.parametrize("authorization", INVALID_AUTH_HEADERS)
def test_spin_requires_bearer_token(
    slots_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    verify_token: Mock,
    authorization: str | None,
) -> None:
    client, db = slots_client()
    headers = {"Authorization": authorization} if authorization is not None else {}

    response = client.post(
        "/api/games/slots/spin",
        json={"bet_amount": 10},
        headers=headers,
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    verify_token.assert_not_called()
    assert db.seen_uids == []


def test_spin_rejects_unverified_email(
    slots_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    verify_token: Mock,
) -> None:
    verify_token.return_value["email_verified"] = False
    client, db = slots_client()

    response = client.post(
        "/api/games/slots/spin",
        json={"bet_amount": 10},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Email verification required"}
    assert db.seen_uids == []


def test_slots_openapi_declares_bearer_on_spin_only(
    slots_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    client, _db = slots_client()
    schema = client.get("/openapi.json").json()

    assert schema["paths"]["/api/games/slots/spin"]["post"]["security"] == [{"HTTPBearer": []}]
    assert "security" not in schema["paths"]["/api/games/slots/config"]["get"]


# --- Atomic Firestore settlement & edge cases ---


def test_winning_spin_settles_credits_and_logs_both_transactions(
    slots_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    # Rolls [0, 99, 10] -> ["cherry", "seven", "cherry"] -> Podwójna wiśnia (2x)
    client, db = slots_client(credits=500, rolls=[0, 99, 10])

    response = client.post(
        "/api/games/slots/spin",
        json={"bet_amount": 25},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "reels": ["cherry", "seven", "cherry"],
        "won": True,
        "matched_combination": {
            "symbol": "cherry",
            "count": 2,
            "multiplier": 2,
            "name": "Podwójna wiśnia",
        },
        "bet_amount": 25,
        "payout": 50,
        "net_profit": 25,
        "new_balance": 525,
    }
    assert db.seen_uids == [DEFAULT_UID]
    assert db.state["credits"] == 525
    assert db.last_transaction is not None
    assert db.last_transaction.committed is True
    assert db.last_transaction.rolled_back is False
    tx_docs = [data for _ref, data in db.state["transactions"]]
    assert tx_docs == [
        {"value": -25.0, "Reason": SlotsService.BET_REASON, "timestamp": SERVER_TIMESTAMP},
        {"value": 50.0, "Reason": SlotsService.WIN_REASON, "timestamp": SERVER_TIMESTAMP},
    ]


def test_losing_spin_deducts_bet_and_logs_only_wager_transaction(
    slots_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    # Rolls [30, 55, 75] -> ["lemon", "orange", "bell"] -> loss
    client, db = slots_client(credits=500, rolls=[30, 55, 75])

    response = client.post(
        "/api/games/slots/spin",
        json={"bet_amount": 20},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "reels": ["lemon", "orange", "bell"],
        "won": False,
        "matched_combination": None,
        "bet_amount": 20,
        "payout": 0,
        "net_profit": -20,
        "new_balance": 480,
    }
    assert db.state["credits"] == 480
    tx_docs = [data for _ref, data in db.state["transactions"]]
    assert tx_docs == [
        {"value": -20.0, "Reason": SlotsService.BET_REASON, "timestamp": SERVER_TIMESTAMP},
    ]


def test_insufficient_credits_returns_400_and_never_mutates_or_leaks_outcome(
    slots_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    client, db = slots_client(credits=15, rolls=[99, 99, 99])

    response = client.post(
        "/api/games/slots/spin",
        json={"bet_amount": 20},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Insufficient credits"}
    assert "reels" not in response.text
    assert db.state["credits"] == 15
    assert db.state["transactions"] == []
    assert db.last_transaction is not None
    assert db.last_transaction.committed is False
    assert db.last_transaction.rolled_back is True


def test_missing_profile_returns_503_and_does_not_leak_spin(
    slots_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    client, db = slots_client(credits=500, exists=False, rolls=[99, 99, 99])

    response = client.post(
        "/api/games/slots/spin",
        json={"bet_amount": 10},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "User profile service unavailable"}
    assert "reels" not in response.text
    assert db.state["transactions"] == []


def test_firestore_error_returns_generic_503(
    slots_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    client, _db = slots_client(
        credits=500,
        rolls=[99, 99, 99],
        get_error=FirestorePermissionDenied("private project configuration"),
    )

    response = client.post(
        "/api/games/slots/spin",
        json={"bet_amount": 10},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "User profile service unavailable"}
    assert "private project configuration" not in response.text


@pytest.mark.parametrize("uid", UNSAFE_UIDS)
def test_unsafe_uid_is_rejected_before_touching_firestore(
    slots_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    verify_token: Mock,
    uid: str,
) -> None:
    verify_token.return_value["uid"] = uid
    client, db = slots_client(credits=500)

    response = client.post(
        "/api/games/slots/spin",
        json={"bet_amount": 10},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 401
    assert db.seen_uids == []
