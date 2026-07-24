"""Tests for profiles table data access."""

import pytest

_USER_ID = "11111111-1111-1111-1111-111111111111"


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, table, *, rows=None, operation="select"):
        self.table = table
        self._rows = list(rows or [])
        self.operation = operation
        self.filters: list[tuple[str, object]] = []
        self.limit_value: int | None = None
        self.upsert_payload: dict | None = None
        self.on_conflict: str | None = None
        self.ignore_duplicates: bool = False
        self.table.client.last_query = self

    def select(self, cols):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def upsert(self, payload, *, on_conflict="", ignore_duplicates=False):
        self.operation = "upsert"
        self.upsert_payload = payload
        self.on_conflict = on_conflict
        self.ignore_duplicates = ignore_duplicates
        return self

    def _matching_rows(self):
        rows = self._rows
        for column, value in self.filters:
            rows = [row for row in rows if row.get(column) == value]
        return rows

    def execute(self):
        import httpx

        self.table.client.execute_attempts += 1
        if self.table.client.execute_failures_remaining > 0:
            self.table.client.execute_failures_remaining -= 1
            raise httpx.ReadTimeout("slow")

        if self.operation == "upsert":
            self.table.client.upsert_calls += 1
            self.table.client.last_upsert = self
            assert self.upsert_payload is not None
            row_id = self.upsert_payload["id"]
            existing = next(
                (row for row in self.table.rows if row.get("id") == row_id),
                None,
            )
            if existing is not None and self.ignore_duplicates:
                return FakeResponse([])
            if existing is None:
                row = {"id": row_id, "tier": "free"}
                self.table.rows.append(row)
                return FakeResponse([row])
            return FakeResponse([existing])

        matching = self._matching_rows()
        if self.limit_value is not None:
            matching = matching[: self.limit_value]
        return FakeResponse(matching)


class FakeTable:
    def __init__(self, client, name, rows):
        self.client = client
        self.name = name
        self.rows = rows

    def select(self, cols):
        return FakeQuery(self, rows=self.rows, operation="select")

    def upsert(self, payload, *, on_conflict="", ignore_duplicates=False):
        return FakeQuery(self, rows=self.rows, operation="upsert").upsert(
            payload,
            on_conflict=on_conflict,
            ignore_duplicates=ignore_duplicates,
        )


class FakeClient:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.last_query: FakeQuery | None = None
        self.last_upsert: FakeQuery | None = None
        self.execute_attempts = 0
        self.execute_failures_remaining = 0
        self.upsert_calls = 0

    def table(self, name):
        assert name == "profiles"
        return FakeTable(self, name, self.rows)


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(
        "profiles_repository.supabase_client.get_service_role_client",
        lambda: client,
    )
    return client


class TestGetOrCreate:
    def test_returns_existing_profile_without_upsert(self, fake_client):
        existing = {"id": _USER_ID, "tier": "pro"}
        fake_client.rows = [existing]

        from profiles_repository import get_or_create

        profile = get_or_create(_USER_ID)

        assert profile == existing
        assert fake_client.upsert_calls == 0

    def test_creates_profile_with_default_tier(self, fake_client):
        from profiles_repository import get_or_create

        profile = get_or_create(_USER_ID)

        assert profile["id"] == _USER_ID
        assert profile["tier"] == "free"
        assert len(fake_client.rows) == 1
        assert fake_client.upsert_calls == 1
        assert fake_client.last_upsert is not None
        assert fake_client.last_upsert.upsert_payload == {"id": _USER_ID}
        assert fake_client.last_upsert.on_conflict == "id"
        assert fake_client.last_upsert.ignore_duplicates is True

    def test_reselects_after_concurrent_create(self, monkeypatch):
        class RacingFakeQuery(FakeQuery):
            def execute(self):
                if self.operation == "upsert":
                    self.table.rows.append({"id": _USER_ID, "tier": "free"})
                    return FakeResponse([])
                return super().execute()

        class RacingFakeTable(FakeTable):
            def select(self, cols):
                return RacingFakeQuery(self, rows=self.rows, operation="select")

            def upsert(self, payload, *, on_conflict="", ignore_duplicates=False):
                return RacingFakeQuery(self, rows=self.rows, operation="upsert").upsert(
                    payload,
                    on_conflict=on_conflict,
                    ignore_duplicates=ignore_duplicates,
                )

        client = FakeClient()
        client.table = lambda name: RacingFakeTable(client, name, client.rows)
        monkeypatch.setattr(
            "profiles_repository.supabase_client.get_service_role_client",
            lambda: client,
        )

        from profiles_repository import get_or_create

        profile = get_or_create(_USER_ID)

        assert profile == {"id": _USER_ID, "tier": "free"}
        assert len(client.rows) == 1

    @pytest.mark.parametrize(
        "user_id",
        ["", "   ", 123, None],
    )
    def test_rejects_invalid_user_id(self, fake_client, user_id):
        from profiles_repository import get_or_create

        with pytest.raises(ValueError, match="user_id is required"):
            get_or_create(user_id)
        assert fake_client.execute_attempts == 0
        assert fake_client.upsert_calls == 0


class TestRetryBehavior:
    def test_retries_read_timeout_on_initial_select(self, fake_client, monkeypatch):
        fake_client.rows = [{"id": _USER_ID, "tier": "pro"}]
        fake_client.execute_failures_remaining = 1
        monkeypatch.setattr("supabase_client.time.sleep", lambda _s: None)

        from profiles_repository import get_or_create

        profile = get_or_create(_USER_ID)

        assert profile["tier"] == "pro"
        assert fake_client.execute_attempts == 2
        assert fake_client.upsert_calls == 0

    def test_get_or_create_does_not_retry_read_timeout(self, fake_client, monkeypatch):
        monkeypatch.setattr("supabase_client.time.sleep", lambda _s: None)

        import httpx

        class FailingUpsertQuery(FakeQuery):
            def execute(self):
                self.table.client.execute_attempts += 1
                self.table.client.upsert_calls += 1
                raise httpx.ReadTimeout("slow")

        class FailingUpsertTable(FakeTable):
            def upsert(self, payload, *, on_conflict="", ignore_duplicates=False):
                return FailingUpsertQuery(
                    self, rows=self.rows, operation="upsert"
                ).upsert(
                    payload,
                    on_conflict=on_conflict,
                    ignore_duplicates=ignore_duplicates,
                )

        fake_client.table = lambda name: FailingUpsertTable(
            fake_client, name, fake_client.rows
        )

        from profiles_repository import get_or_create

        with pytest.raises(httpx.ReadTimeout):
            get_or_create(_USER_ID)
        assert fake_client.execute_attempts == 2
        assert fake_client.upsert_calls == 1
