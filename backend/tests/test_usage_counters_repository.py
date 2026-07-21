"""Tests for usage_counters table data access."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

_USER_ID = "11111111-1111-1111-1111-111111111111"
_OTHER_USER_ID = "22222222-2222-2222-2222-222222222222"
_PERIOD = "2026-07"


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
        self.table.client.last_query = self

    def select(self, cols):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def limit(self, value):
        self.limit_value = value
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


class FakeRpc:
    def __init__(self, client, fn_name, params):
        self.client = client
        self.fn_name = fn_name
        self.params = params
        self.client.last_rpc = self

    def execute(self):
        import httpx

        self.client.execute_attempts += 1
        if self.client.execute_failures_remaining > 0:
            self.client.execute_failures_remaining -= 1
            raise httpx.ConnectError("network down")

        if self.fn_name != "increment_usage_counter":
            raise AssertionError(f"unexpected rpc: {self.fn_name}")

        user_id = self.params["p_user_id"]
        period = self.params["p_period"]
        for row in self.client.rows:
            if row["user_id"] == user_id and row["period"] == period:
                row["count"] += 1
                return FakeResponse([row])

        row = {"user_id": user_id, "period": period, "count": 1}
        self.client.rows.append(row)
        return FakeResponse([row])


class FakeClient:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.last_query: FakeQuery | None = None
        self.last_rpc: FakeRpc | None = None
        self.execute_attempts = 0
        self.execute_failures_remaining = 0

    def table(self, name):
        assert name == "usage_counters"
        return FakeTable(self, name, self.rows)

    def rpc(self, fn_name, params):
        return FakeRpc(self, fn_name, params)


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(
        "usage_counters_repository.supabase_client.get_service_role_client",
        lambda: client,
    )
    return client


class TestIncrement:
    def test_creates_row_with_count_one(self, fake_client):
        from usage_counters_repository import increment

        row = increment(_USER_ID, period=_PERIOD)

        assert row["user_id"] == _USER_ID
        assert row["period"] == _PERIOD
        assert row["count"] == 1
        assert len(fake_client.rows) == 1

    def test_increments_existing_row(self, fake_client):
        fake_client.rows = [
            {"user_id": _USER_ID, "period": _PERIOD, "count": 3},
        ]

        from usage_counters_repository import increment

        row = increment(_USER_ID, period=_PERIOD)

        assert row["count"] == 4
        assert len(fake_client.rows) == 1

    def test_defaults_period_to_current_utc_month(self, fake_client, monkeypatch):
        fixed_now = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
        mock_datetime = MagicMock(wraps=datetime)
        mock_datetime.now.return_value = fixed_now
        monkeypatch.setattr("usage_counters_repository.datetime", mock_datetime)

        from usage_counters_repository import increment

        row = increment(_USER_ID)

        assert row["period"] == "2026-07"
        assert fake_client.last_rpc is not None
        assert fake_client.last_rpc.params["p_period"] == "2026-07"
        mock_datetime.now.assert_called_once_with(timezone.utc)

    def test_passes_user_id_and_period_to_rpc(self, fake_client):
        from usage_counters_repository import increment

        increment(_USER_ID, period=_PERIOD)

        assert fake_client.last_rpc is not None
        assert fake_client.last_rpc.fn_name == "increment_usage_counter"
        assert fake_client.last_rpc.params == {
            "p_user_id": _USER_ID,
            "p_period": _PERIOD,
        }

    def test_rejects_missing_user_id(self, fake_client):
        from usage_counters_repository import increment

        with pytest.raises(ValueError, match="user_id is required"):
            increment("", period=_PERIOD)
        assert fake_client.last_rpc is None

    def test_rejects_invalid_period(self, fake_client):
        from usage_counters_repository import increment

        with pytest.raises(ValueError, match="period must be in YYYY-MM format"):
            increment(_USER_ID, period="2026-13")
        assert fake_client.last_rpc is None

    def test_rejects_short_period(self, fake_client):
        from usage_counters_repository import increment

        with pytest.raises(ValueError, match="period must be in YYYY-MM format"):
            increment(_USER_ID, period="26-07")
        assert fake_client.last_rpc is None


class TestRead:
    def test_returns_zero_when_no_row(self, fake_client):
        from usage_counters_repository import read

        assert read(_USER_ID, period=_PERIOD) == 0

    def test_returns_stored_count(self, fake_client):
        fake_client.rows = [
            {"user_id": _USER_ID, "period": _PERIOD, "count": 5},
        ]

        from usage_counters_repository import read

        assert read(_USER_ID, period=_PERIOD) == 5

    def test_defaults_period_to_current_utc_month(self, fake_client, monkeypatch):
        fixed_now = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
        mock_datetime = MagicMock(wraps=datetime)
        mock_datetime.now.return_value = fixed_now
        monkeypatch.setattr("usage_counters_repository.datetime", mock_datetime)
        fake_client.rows = [
            {"user_id": _USER_ID, "period": "2026-07", "count": 5},
        ]

        from usage_counters_repository import read

        assert read(_USER_ID) == 5
        assert fake_client.last_query is not None
        assert ("period", "2026-07") in fake_client.last_query.filters
        mock_datetime.now.assert_called_once_with(timezone.utc)

    def test_filters_by_user_id_and_period(self, fake_client):
        fake_client.rows = [
            {"user_id": _USER_ID, "period": _PERIOD, "count": 5},
            {"user_id": _OTHER_USER_ID, "period": _PERIOD, "count": 9},
            {"user_id": _USER_ID, "period": "2026-08", "count": 2},
        ]

        from usage_counters_repository import read

        read(_USER_ID, period=_PERIOD)

        assert fake_client.last_query is not None
        assert ("user_id", _USER_ID) in fake_client.last_query.filters
        assert ("period", _PERIOD) in fake_client.last_query.filters
        assert fake_client.last_query.limit_value == 1

    def test_rejects_missing_user_id(self, fake_client):
        from usage_counters_repository import read

        with pytest.raises(ValueError, match="user_id is required"):
            read("", period=_PERIOD)
        assert fake_client.last_query is None

    def test_rejects_invalid_period(self, fake_client):
        from usage_counters_repository import read

        with pytest.raises(ValueError, match="period must be in YYYY-MM format"):
            read(_USER_ID, period="2026-13")
        assert fake_client.last_query is None


class TestRetryBehavior:
    def test_read_retries_read_timeout(self, fake_client, monkeypatch):
        fake_client.rows = [
            {"user_id": _USER_ID, "period": _PERIOD, "count": 5},
        ]
        fake_client.execute_failures_remaining = 1
        monkeypatch.setattr("supabase_client.time.sleep", lambda _s: None)

        from usage_counters_repository import read

        assert read(_USER_ID, period=_PERIOD) == 5
        assert fake_client.execute_attempts == 2

    def test_increment_retries_connect_error(self, fake_client, monkeypatch):
        fake_client.execute_failures_remaining = 1
        monkeypatch.setattr("supabase_client.time.sleep", lambda _s: None)

        from usage_counters_repository import increment

        row = increment(_USER_ID, period=_PERIOD)
        assert row["count"] == 1
        assert fake_client.execute_attempts == 2

    def test_increment_does_not_retry_read_timeout(self, fake_client, monkeypatch):
        monkeypatch.setattr("supabase_client.time.sleep", lambda _s: None)

        import httpx

        class FailingRpc(FakeRpc):
            def execute(self):
                raise httpx.ReadTimeout("slow")

        def rpc(fn_name, params):
            return FailingRpc(fake_client, fn_name, params)

        fake_client.rpc = rpc

        from usage_counters_repository import increment

        with pytest.raises(httpx.ReadTimeout):
            increment(_USER_ID, period=_PERIOD)
