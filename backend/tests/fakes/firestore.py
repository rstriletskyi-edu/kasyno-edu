from collections.abc import Callable
from datetime import datetime, timezone
from unittest.mock import Mock

from google.api_core.exceptions import AlreadyExists
from google.cloud.firestore import SERVER_TIMESTAMP

DEFAULT_CREATED_AT = datetime(2026, 11, 12, tzinfo=timezone.utc)


class FakeTransactionRef:
    """Simulated Firestore document reference under users/{uid}/transactions."""

    def __init__(self, doc_id: str, state: dict[str, object]) -> None:
        self.id = doc_id
        self._state = state

    def create(self, data: dict[str, object]) -> None:
        self._state["direct_transactions"].append((self.id, dict(data)))


class FakeTransaction:
    """In-memory Transaction compatible with google.cloud.firestore.transactional.

    Intentionally omits `.get()` so any regression back to `transaction.get(ref)`
    fails immediately instead of hiding the SDK generator bug.
    """

    def __init__(
        self,
        state: dict[str, object],
        commit_errors: list[Exception] | None = None,
        on_retry: Callable[[int, dict[str, object]], None] | None = None,
    ) -> None:
        self._state = state
        self._commit_errors = list(commit_errors or [])
        self._on_retry = on_retry
        self._max_attempts = 5
        self._read_only = False
        self._id = b"fake-tx-id"
        self.attempts = 0
        self.updates: list[tuple[object, dict[str, object]]] = []
        self.creates: list[tuple[FakeTransactionRef, dict[str, object]]] = []
        self.committed = False
        self.rolled_back = False

    def _clean_up(self) -> None:
        self.updates.clear()
        self.creates.clear()

    def _begin(self, retry_id: object = None) -> None:
        self.attempts += 1

    def update(self, reference: object, fields: dict[str, object]) -> None:
        self.updates.append((reference, dict(fields)))

    def create(self, reference: FakeTransactionRef, data: dict[str, object]) -> None:
        self.creates.append((reference, dict(data)))

    def _commit(self) -> None:
        if self._commit_errors:
            err = self._commit_errors.pop(0)
            if self._on_retry is not None:
                self._on_retry(self.attempts, self._state)
            raise err
        for _ref, fields in self.updates:
            self._state["credits"] = fields["credits"]
        for ref, data in self.creates:
            self._state["transactions"].append((ref.id, data))
        self.committed = True

    def _rollback(self) -> None:
        self.updates.clear()
        self.creates.clear()
        self.rolled_back = True


class FakeTransactionsCollection:
    def __init__(self, state: dict[str, object]) -> None:
        self._state = state

    def document(self) -> FakeTransactionRef:
        seq = self._state["next_tx_id"]
        self._state["next_tx_id"] = seq + 1
        return FakeTransactionRef(f"tx-{seq}", self._state)


class FakeUserDocument:
    def __init__(self, state: dict[str, object]) -> None:
        self._state = state
        self.seen_transactions: list[object] = []
        self.create_calls: list[dict[str, object]] = []
        self.set_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.update_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def get(self, transaction: FakeTransaction | None = None) -> Mock:
        self.seen_transactions.append(transaction)
        error = self._state.get("get_error")
        if error is not None:
            raise error
        snapshot = Mock(exists=self._state["exists"])
        if self._state["exists"]:
            data = dict(self._state["doc_data"])
            if "credits" in self._state:
                data["credits"] = self._state["credits"]
            snapshot.to_dict.return_value = data
        else:
            snapshot.to_dict.return_value = None
        return snapshot

    def create(self, data: dict[str, object]) -> None:
        self.create_calls.append(dict(data))
        error = self._state.get("create_error")
        if error is not None:
            raise error
        if self._state["exists"]:
            raise AlreadyExists("Profile already exists")
        self._state["exists"] = True
        doc_data = dict(self._state["doc_data"])
        created_at = data.get("created_at")
        if created_at is SERVER_TIMESTAMP:
            doc_data["created_at"] = DEFAULT_CREATED_AT
        elif created_at is not None:
            doc_data["created_at"] = created_at
        for key, value in data.items():
            if key not in {"created_at", "credits"}:
                doc_data[key] = value
        self._state["doc_data"] = doc_data
        if "credits" in data:
            self._state["credits"] = data["credits"]

    def set(self, *args: object, **kwargs: object) -> None:
        self.set_calls.append((args, kwargs))

    def update(self, *args: object, **kwargs: object) -> None:
        self.update_calls.append((args, kwargs))

    def collection(self, name: str) -> FakeTransactionsCollection:
        assert name == "transactions"
        return FakeTransactionsCollection(self._state)


class FakeFirestoreDB:
    def __init__(
        self,
        credits: int = 500,
        exists: bool = True,
        created_at: datetime | None = DEFAULT_CREATED_AT,
        extra_fields: dict[str, object] | None = None,
        include_credits_field: bool = True,
        commit_errors: list[Exception] | None = None,
        on_retry: Callable[[int, dict[str, object]], None] | None = None,
        get_error: Exception | None = None,
        create_error: Exception | None = None,
    ) -> None:
        doc_data: dict[str, object] = {}
        if exists and created_at is not None:
            doc_data["created_at"] = created_at
        if extra_fields:
            doc_data.update(extra_fields)

        self.state: dict[str, object] = {
            "exists": exists,
            "doc_data": doc_data,
            "transactions": [],
            "direct_transactions": [],
            "next_tx_id": 1,
            "get_error": get_error,
            "create_error": create_error,
        }
        if include_credits_field:
            self.state["credits"] = credits
        self.seen_uids: list[str] = []
        self.transactions: list[FakeTransaction] = []
        self._commit_errors = commit_errors
        self._on_retry = on_retry
        self.user_doc = FakeUserDocument(self.state)

    @property
    def last_transaction(self) -> FakeTransaction | None:
        return self.transactions[-1] if self.transactions else None

    def collection(self, name: str) -> Mock:
        assert name == "users"
        users_col = Mock()

        def get_doc(uid: str) -> FakeUserDocument:
            self.seen_uids.append(uid)
            return self.user_doc

        users_col.document.side_effect = get_doc
        return users_col

    def transaction(self) -> FakeTransaction:
        tx = FakeTransaction(
            self.state,
            commit_errors=self._commit_errors,
            on_retry=self._on_retry,
        )
        self.transactions.append(tx)
        return tx
