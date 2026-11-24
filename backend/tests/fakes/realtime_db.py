class FakeRealtimeRef:
    """In-memory Firebase Realtime Database reference for testing."""

    def __init__(self, data: object) -> None:
        self._data = data

    def child(self, path: str) -> "FakeRealtimeRef":
        current = self._data
        for segment in path.split("/"):
            if not segment:
                continue
            if not isinstance(current, dict):
                return FakeRealtimeRef(None)
            current = current.get(segment)
        return FakeRealtimeRef(current)

    def get(self) -> object:
        return self._data
