from collections.abc import Callable
from unittest.mock import Mock

from fastapi.testclient import TestClient
from google.api_core.exceptions import PermissionDenied as FirestorePermissionDenied
from google.cloud.firestore import SERVER_TIMESTAMP
import pytest

from src.configs.games.ruleta import RuletaSettings
from src.dependencies import get_ruleta_service
from src.services.games.ruleta_service import RuletaService
from src.services.user_service import UserService
from tests.fakes.auth import AUTH_HEADERS, DEFAULT_UID, INVALID_AUTH_HEADERS, UNSAFE_UIDS
from tests.fakes.firestore import FakeFirestoreDB


@pytest.fixture
def ruleta_client(
    make_client: Callable[..., TestClient],
    make_firestore_db: Callable[..., FakeFirestoreDB],
    verify_token: Mock,
) -> Callable[..., tuple[TestClient, FakeFirestoreDB]]:
    def _open(
        credits: int = 500,
        exists: bool = True,
        winning_number: int = 7,
        settings: RuletaSettings | None = None,
        get_error: Exception | None = None,
    ) -> tuple[TestClient, FakeFirestoreDB]:
        db = make_firestore_db(credits=credits, exists=exists, get_error=get_error)
        service = RuletaService(
            user_service=UserService(db),
            settings=settings or RuletaSettings(_env_file=None),
            rng=lambda: winning_number,
        )
        client = make_client(dependency_overrides={get_ruleta_service: lambda: service})
        return client, db

    return _open


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
    ruleta_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    payload: dict[str, object],
) -> None:
    client, db = ruleta_client(credits=10000)

    response = client.post("/api/games/ruleta/spin", json=payload, headers=AUTH_HEADERS)

    assert response.status_code == 422
    assert db.seen_uids == []


def test_total_bet_exact_limit_is_accepted(
    ruleta_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    client, db = ruleta_client(credits=10000, winning_number=7)

    response = client.post(
        "/api/games/ruleta/spin",
        json={"bets": [{"bet_type": "red", "amount": 1000}] * 5},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["total_bet"] == 5000
    assert db.state["credits"] == 15000


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
    ruleta_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    bets: list[dict[str, object]],
    expected_detail: str,
) -> None:
    custom = RuletaSettings(
        _env_file=None,
        min_bet_amount=5,
        max_bet_amount=50,
        max_total_bet=80,
        max_bets_per_spin=2,
    )
    client, db = ruleta_client(credits=500, winning_number=7, settings=custom)

    rejected = client.post("/api/games/ruleta/spin", json={"bets": bets}, headers=AUTH_HEADERS)

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
        headers=AUTH_HEADERS,
    )
    assert allowed.status_code == 200
    assert allowed.json()["total_bet"] == 80


@pytest.mark.parametrize("authorization", INVALID_AUTH_HEADERS)
def test_spin_requires_bearer_token(
    ruleta_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    verify_token: Mock,
    authorization: str | None,
) -> None:
    client, db = ruleta_client()
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
    ruleta_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    verify_token: Mock,
) -> None:
    verify_token.return_value["email_verified"] = False
    client, db = ruleta_client()

    response = client.post(
        "/api/games/ruleta/spin",
        json={"bets": [{"bet_type": "red", "amount": 10}]},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Email verification required"}
    assert db.seen_uids == []


def test_spin_openapi_declares_bearer_authentication(
    ruleta_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    client, _db = ruleta_client()
    schema = client.get("/openapi.json").json()

    assert schema["paths"]["/api/games/ruleta/spin"]["post"]["security"] == [{"HTTPBearer": []}]
    assert "/api/games/ruleta/rules" not in schema["paths"]


def test_winning_spin_settles_credits_and_logs_both_transactions(
    ruleta_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    # 7 is red
    client, db = ruleta_client(credits=500, winning_number=7)

    response = client.post(
        "/api/games/ruleta/spin",
        json={"bets": [{"bet_type": "straight", "numbers": [7], "amount": 10}]},
        headers=AUTH_HEADERS,
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
    assert db.seen_uids == [DEFAULT_UID]
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
    ruleta_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    # 15 is black
    client, db = ruleta_client(credits=500, winning_number=15)

    response = client.post(
        "/api/games/ruleta/spin",
        json={"bets": [{"bet_type": "red", "amount": 25}]},
        headers=AUTH_HEADERS,
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
    ruleta_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    # 2 is black, even, low (1-18). Bet 25 on red (loses) + 25 on black (wins 50) -> net 0.
    client, db = ruleta_client(credits=500, winning_number=2)

    response = client.post(
        "/api/games/ruleta/spin",
        json={
            "bets": [
                {"bet_type": "red", "amount": 25},
                {"bet_type": "black", "amount": 25},
            ]
        },
        headers=AUTH_HEADERS,
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
    ruleta_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    client, db = ruleta_client(credits=40, winning_number=7)

    response = client.post(
        "/api/games/ruleta/spin",
        json={
            "bets": [
                {"bet_type": "red", "amount": 25},
                {"bet_type": "straight", "numbers": [7], "amount": 25},
            ]
        },
        headers=AUTH_HEADERS,
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
    ruleta_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    client, db = ruleta_client(credits=500, exists=False, winning_number=7)

    response = client.post(
        "/api/games/ruleta/spin",
        json={"bets": [{"bet_type": "red", "amount": 10}]},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "User profile service unavailable"}
    assert "winning_number" not in response.text
    assert db.state["transactions"] == []


def test_firestore_error_returns_generic_503(
    ruleta_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    client, _db = ruleta_client(
        credits=500,
        winning_number=7,
        get_error=FirestorePermissionDenied("private project configuration"),
    )

    response = client.post(
        "/api/games/ruleta/spin",
        json={"bets": [{"bet_type": "red", "amount": 10}]},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "User profile service unavailable"}
    assert "private project configuration" not in response.text


@pytest.mark.parametrize("uid", UNSAFE_UIDS)
def test_unsafe_uid_is_rejected_before_touching_firestore(
    ruleta_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    verify_token: Mock,
    uid: str,
) -> None:
    verify_token.return_value["uid"] = uid
    client, db = ruleta_client(credits=500)

    response = client.post(
        "/api/games/ruleta/spin",
        json={"bets": [{"bet_type": "red", "amount": 10}]},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 401
    assert db.seen_uids == []
