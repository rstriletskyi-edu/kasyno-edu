from collections.abc import Callable
from unittest.mock import Mock

from fastapi.testclient import TestClient
from google.api_core.exceptions import PermissionDenied as FirestorePermissionDenied
from google.cloud.firestore import SERVER_TIMESTAMP
import pytest

from src.configs.games.blackjack import BlackjackSettings
from src.dependencies import get_blackjack_service
from src.services.games.blackjack_rules import Card, Rank, Suit
from src.services.games.blackjack_service import BlackjackService, BlackjackSessionStore
from src.services.user_service import UserService
from tests.fakes.auth import AUTH_HEADERS, DEFAULT_UID, INVALID_AUTH_HEADERS, UNSAFE_UIDS
from tests.fakes.firestore import FakeFirestoreDB


def c(rank: Rank, suit: Suit = Suit.SPADES) -> Card:
    return Card(rank=rank, suit=suit)


@pytest.fixture
def blackjack_client(
    make_client: Callable[..., TestClient],
    make_firestore_db: Callable[..., FakeFirestoreDB],
    verify_token: Mock,
) -> Callable[..., tuple[TestClient, FakeFirestoreDB]]:
    def _open(
        credits: int = 500,
        exists: bool = True,
        cards: list[Card] | None = None,
        settings: BlackjackSettings | None = None,
        get_error: Exception | None = None,
    ) -> tuple[TestClient, FakeFirestoreDB]:
        db = make_firestore_db(credits=credits, exists=exists, get_error=get_error)
        resolved_settings = settings or BlackjackSettings(_env_file=None)
        scripted = list(
            cards
            or [
                c(Rank.SIX),
                c(Rank.TEN),
                c(Rank.FIVE),
                c(Rank.EIGHT),
                c(Rank.SEVEN),
                c(Rank.TWO),
            ]
        )
        store = BlackjackSessionStore()
        service = BlackjackService(
            user_service=UserService(db),
            settings=resolved_settings,
            store=store,
            deck_factory=lambda _decks: list(scripted),
        )
        client = make_client(dependency_overrides={get_blackjack_service: lambda: service})
        return client, db

    return _open


# --- Auth & OpenAPI ---


@pytest.mark.parametrize("authorization", INVALID_AUTH_HEADERS)
@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/api/games/blackjack/start", {"bet_amount": 10}),
        ("GET", "/api/games/blackjack/missing-id", None),
        ("POST", "/api/games/blackjack/missing-id/hit", None),
        ("POST", "/api/games/blackjack/missing-id/stand", None),
        ("POST", "/api/games/blackjack/missing-id/double", None),
    ],
)
def test_blackjack_routes_require_bearer_token(
    blackjack_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    verify_token: Mock,
    authorization: str | None,
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> None:
    client, db = blackjack_client()
    headers = {"Authorization": authorization} if authorization is not None else {}

    response = client.request(method, path, json=body, headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    verify_token.assert_not_called()
    assert db.seen_uids == []


def test_blackjack_rejects_unverified_email(
    blackjack_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    verify_token: Mock,
) -> None:
    verify_token.return_value["email_verified"] = False
    client, db = blackjack_client()

    response = client.post(
        "/api/games/blackjack/start",
        json={"bet_amount": 10},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Email verification required"}
    assert db.seen_uids == []


def test_blackjack_openapi_declares_bearer_on_all_routes(
    blackjack_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    client, _db = blackjack_client()
    schema = client.get("/openapi.json").json()

    assert schema["paths"]["/api/games/blackjack/start"]["post"]["security"] == [{"HTTPBearer": []}]
    assert schema["paths"]["/api/games/blackjack/{game_id}"]["get"]["security"] == [{"HTTPBearer": []}]
    assert schema["paths"]["/api/games/blackjack/{game_id}/hit"]["post"]["security"] == [{"HTTPBearer": []}]
    assert schema["paths"]["/api/games/blackjack/{game_id}/stand"]["post"]["security"] == [{"HTTPBearer": []}]
    assert schema["paths"]["/api/games/blackjack/{game_id}/double"]["post"]["security"] == [{"HTTPBearer": []}]


@pytest.mark.parametrize("uid", UNSAFE_UIDS)
def test_unsafe_uid_is_rejected_before_touching_firestore(
    blackjack_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    verify_token: Mock,
    uid: str,
) -> None:
    verify_token.return_value["uid"] = uid
    client, db = blackjack_client(credits=500)

    response = client.post(
        "/api/games/blackjack/start",
        json={"bet_amount": 10},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 401
    assert db.seen_uids == []


# --- Validation & configurable limits ---


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"bet_amount": 0},
        {"bet_amount": -5},
        {"bet_amount": 1001},
        {"bet_amount": True},
        {"bet_amount": 10.5},
        {"bet_amount": "10"},
        {"bet_amount": 10, "payout": 9999},
        {"bet_amount": 10, "uid": "victim"},
    ],
)
def test_start_rejects_tampered_or_invalid_payloads(
    blackjack_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    payload: dict[str, object],
) -> None:
    client, db = blackjack_client(credits=5000)

    response = client.post("/api/games/blackjack/start", json=payload, headers=AUTH_HEADERS)

    assert response.status_code == 422
    assert db.seen_uids == []


@pytest.mark.parametrize(
    ("bet_amount", "expected_detail"),
    [
        (4, "Bet amount must be at least 5"),
        (51, "Bet amount cannot exceed 50"),
    ],
)
def test_custom_blackjack_settings_enforce_limits_before_firestore(
    blackjack_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    bet_amount: int,
    expected_detail: str,
) -> None:
    custom = BlackjackSettings(_env_file=None, min_bet_amount=5, max_bet_amount=50)
    client, db = blackjack_client(credits=500, settings=custom)

    rejected = client.post(
        "/api/games/blackjack/start",
        json={"bet_amount": bet_amount},
        headers=AUTH_HEADERS,
    )

    assert rejected.status_code == 422
    assert rejected.json() == {"detail": expected_detail}
    assert db.seen_uids == []

    allowed = client.post(
        "/api/games/blackjack/start",
        json={"bet_amount": 50},
        headers=AUTH_HEADERS,
    )
    assert allowed.status_code == 201
    assert allowed.json()["bet_amount"] == 50


# --- Gameplay flows & Firestore settlement ---


def test_full_start_get_hit_stand_flow_and_transactions(
    blackjack_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    # Deal: p1=6, d1=10, p2=5, d2=8 (dealer=18), hit=8 (player=19)
    client, db = blackjack_client(
        credits=500,
        cards=[
            c(Rank.SIX),
            c(Rank.TEN),
            c(Rank.FIVE),
            c(Rank.EIGHT),
            c(Rank.EIGHT),
        ],
    )

    start_res = client.post(
        "/api/games/blackjack/start",
        json={"bet_amount": 25},
        headers=AUTH_HEADERS,
    )
    assert start_res.status_code == 201
    assert start_res.headers["cache-control"] == "no-store"
    start_body = start_res.json()
    game_id = start_body["game_id"]
    assert start_body["status"] == "in_progress"
    assert start_body["dealer_hidden_cards"] == 1
    assert len(start_body["dealer_cards"]) == 1
    assert start_body["new_balance"] == 475

    # Read current state via GET
    get_res = client.get(f"/api/games/blackjack/{game_id}", headers=AUTH_HEADERS)
    assert get_res.status_code == 200
    assert get_res.headers["cache-control"] == "no-store"
    assert get_res.json()["player_value"] == 11

    # Hit -> 19
    hit_res = client.post(f"/api/games/blackjack/{game_id}/hit", headers=AUTH_HEADERS)
    assert hit_res.status_code == 200
    assert hit_res.headers["cache-control"] == "no-store"
    assert hit_res.json()["player_value"] == 19
    assert hit_res.json()["available_actions"] == ["hit", "stand"]

    # Stand -> 19 beats 18
    stand_res = client.post(f"/api/games/blackjack/{game_id}/stand", headers=AUTH_HEADERS)
    assert stand_res.status_code == 200
    assert stand_res.headers["cache-control"] == "no-store"
    stand_body = stand_res.json()
    assert stand_body["status"] == "finished"
    assert stand_body["outcome"] == "player_win"
    assert stand_body["dealer_hidden_cards"] == 0
    assert len(stand_body["dealer_cards"]) == 2
    assert stand_body["payout"] == 50
    assert stand_body["net_profit"] == 25
    assert stand_body["new_balance"] == 525
    assert db.seen_uids == [DEFAULT_UID, DEFAULT_UID]
    assert db.state["credits"] == 525
    tx_docs = [data for _ref, data in db.state["transactions"]]
    assert tx_docs == [
        {"value": -25.0, "Reason": BlackjackService.BET_REASON, "timestamp": SERVER_TIMESTAMP},
        {"value": 50.0, "Reason": BlackjackService.WIN_REASON, "timestamp": SERVER_TIMESTAMP},
    ]

    # Action on finished game returns 409
    again = client.post(f"/api/games/blackjack/{game_id}/stand", headers=AUTH_HEADERS)
    assert again.status_code == 409


def test_double_down_http_flow(
    blackjack_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    # Deal: p1=6, d1=9, p2=5, d2=8 (dealer=17), double=9 (player=20)
    client, db = blackjack_client(
        credits=500,
        cards=[c(Rank.SIX), c(Rank.NINE), c(Rank.FIVE), c(Rank.EIGHT), c(Rank.NINE)],
    )
    started = client.post(
        "/api/games/blackjack/start", json={"bet_amount": 30}, headers=AUTH_HEADERS
    )
    game_id = started.json()["game_id"]

    doubled = client.post(f"/api/games/blackjack/{game_id}/double", headers=AUTH_HEADERS)
    assert doubled.status_code == 200
    assert doubled.headers["cache-control"] == "no-store"
    body = doubled.json()
    assert body["status"] == "finished"
    assert body["outcome"] == "player_win"
    assert body["bet_amount"] == 60
    assert body["payout"] == 120
    assert body["net_profit"] == 60
    assert body["new_balance"] == 560
    assert db.state["credits"] == 560


def test_insufficient_credits_returns_400_and_never_leaks_cards(
    blackjack_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    client, db = blackjack_client(credits=15)

    response = client.post(
        "/api/games/blackjack/start",
        json={"bet_amount": 20},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Insufficient credits"}
    assert "player_cards" not in response.text
    assert db.state["credits"] == 15
    assert db.state["transactions"] == []


def test_missing_profile_and_firestore_errors_return_generic_503(
    blackjack_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    missing_client, _ = blackjack_client(credits=500, exists=False)
    missing_res = missing_client.post(
        "/api/games/blackjack/start", json={"bet_amount": 10}, headers=AUTH_HEADERS
    )
    assert missing_res.status_code == 503
    assert missing_res.json() == {"detail": "User profile service unavailable"}
    assert "player_cards" not in missing_res.text

    err_client, _ = blackjack_client(
        credits=500,
        get_error=FirestorePermissionDenied("private project configuration"),
    )
    err_res = err_client.post(
        "/api/games/blackjack/start", json={"bet_amount": 10}, headers=AUTH_HEADERS
    )
    assert err_res.status_code == 503
    assert err_res.json() == {"detail": "User profile service unavailable"}
    assert "private project configuration" not in err_res.text


def test_unknown_game_id_returns_404(
    blackjack_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    client, _ = blackjack_client()
    assert client.get("/api/games/blackjack/does-not-exist", headers=AUTH_HEADERS).status_code == 404
    assert client.post("/api/games/blackjack/does-not-exist/hit", headers=AUTH_HEADERS).status_code == 404
