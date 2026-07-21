"""Tests for analyses table data access."""

import pytest

_USER_ID = "11111111-1111-1111-1111-111111111111"
_OTHER_USER_ID = "22222222-2222-2222-2222-222222222222"
_ANALYSIS_ID = "33333333-3333-3333-3333-333333333333"


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, table, *, rows=None, operation="select"):
        self.table = table
        self._rows = list(rows or [])
        self.operation = operation
        self.filters: list[tuple[str, object]] = []
        self.order_args: tuple | None = None
        self.limit_value: int | None = None
        self.insert_payload: dict | None = None
        self.table.client.last_query = self

    def select(self, cols):
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.insert_payload = payload
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def order(self, column, *, desc=False):
        self.order_args = (column, desc)
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
        if self.operation == "insert":
            row = {"id": _ANALYSIS_ID, **self.insert_payload}
            self.table.rows.append(row)
            return FakeResponse([row])

        matching = self._matching_rows()

        if self.operation == "delete":
            if self.limit_value is not None:
                matching = matching[: self.limit_value]
            for row in matching:
                self.table.rows.remove(row)
            return FakeResponse(matching)

        if self.order_args == ("created_at", True):
            matching = sorted(
                matching,
                key=lambda row: row.get("created_at", ""),
                reverse=True,
            )
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

    def insert(self, payload):
        return FakeQuery(self, rows=self.rows, operation="insert").insert(payload)

    def delete(self):
        return FakeQuery(self, rows=self.rows, operation="delete")


class FakeClient:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.last_query: FakeQuery | None = None

    def table(self, name):
        assert name == "analyses"
        return FakeTable(self, name, self.rows)


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(
        "analyses_repository.supabase_client.get_service_role_client",
        lambda: client,
    )
    return client


class TestCreate:
    def test_inserts_row_for_user(self, fake_client):
        from analyses_repository import create

        row = create(
            user_id=_USER_ID,
            type="stock",
            result={"pnl": 100},
            summary_return=12.5,
            instrument_count=3,
        )

        assert row["user_id"] == _USER_ID
        assert row["type"] == "stock"
        assert row["result"] == {"pnl": 100}
        assert row["summary_return"] == 12.5
        assert row["instrument_count"] == 3
        assert len(fake_client.rows) == 1

    def test_omits_optional_fields_when_none(self, fake_client):
        from analyses_repository import create

        create(user_id=_USER_ID, type="options", result={"pnl": 0})

        assert fake_client.last_query is not None
        assert "summary_return" not in fake_client.last_query.insert_payload
        assert "instrument_count" not in fake_client.last_query.insert_payload

    def test_rejects_missing_user_id(self, fake_client):
        from analyses_repository import create

        with pytest.raises(ValueError, match="user_id is required"):
            create(user_id="", type="stock", result={})
        assert fake_client.last_query is None

    def test_rejects_missing_type(self, fake_client):
        from analyses_repository import create

        with pytest.raises(ValueError, match="type is required"):
            create(user_id=_USER_ID, type="", result={})
        assert fake_client.last_query is None

    def test_rejects_non_dict_result(self, fake_client):
        from analyses_repository import create

        with pytest.raises(ValueError, match="result must be a dict"):
            create(user_id=_USER_ID, type="stock", result=[])
        assert fake_client.last_query is None


class TestListForUser:
    def test_returns_rows_newest_first(self, fake_client):
        fake_client.rows = [
            {
                "id": "a",
                "user_id": _USER_ID,
                "created_at": "2024-01-01T00:00:00Z",
            },
            {
                "id": "b",
                "user_id": _USER_ID,
                "created_at": "2024-02-01T00:00:00Z",
            },
            {
                "id": "c",
                "user_id": _OTHER_USER_ID,
                "created_at": "2024-03-01T00:00:00Z",
            },
        ]

        from analyses_repository import list_for_user

        rows = list_for_user(_USER_ID, limit=10)
        assert [row["id"] for row in rows] == ["b", "a"]
        assert fake_client.last_query is not None
        assert ("user_id", _USER_ID) in fake_client.last_query.filters
        assert fake_client.last_query.order_args == ("created_at", True)
        assert fake_client.last_query.limit_value == 10

    def test_returns_empty_list_when_none_found(self, fake_client):
        from analyses_repository import list_for_user

        assert list_for_user(_USER_ID) == []

    def test_rejects_invalid_limit(self, fake_client):
        from analyses_repository import list_for_user

        with pytest.raises(ValueError, match="limit must be"):
            list_for_user(_USER_ID, limit=0)
        assert fake_client.last_query is None

    def test_rejects_limit_above_max(self, fake_client):
        from analyses_repository import list_for_user

        with pytest.raises(ValueError, match="limit must be"):
            list_for_user(_USER_ID, limit=201)
        assert fake_client.last_query is None

    def test_rejects_bool_limit(self, fake_client):
        from analyses_repository import list_for_user

        with pytest.raises(ValueError, match="limit must be"):
            list_for_user(_USER_ID, limit=True)
        assert fake_client.last_query is None

    def test_excludes_other_users_rows(self, fake_client):
        fake_client.rows = [
            {
                "id": "a",
                "user_id": _OTHER_USER_ID,
                "created_at": "2024-03-01T00:00:00Z",
            },
            {
                "id": "b",
                "user_id": _OTHER_USER_ID,
                "created_at": "2024-02-01T00:00:00Z",
            },
        ]

        from analyses_repository import list_for_user

        assert list_for_user(_USER_ID) == []


class TestGetForUser:
    def test_returns_row_for_owner(self, fake_client):
        fake_client.rows = [
            {"id": _ANALYSIS_ID, "user_id": _USER_ID, "type": "stock"},
        ]

        from analyses_repository import get_for_user

        row = get_for_user(_ANALYSIS_ID, _USER_ID)
        assert row == fake_client.rows[0]

    def test_returns_none_when_missing(self, fake_client):
        from analyses_repository import get_for_user

        assert get_for_user(_ANALYSIS_ID, _USER_ID) is None

    def test_returns_none_for_other_users_row(self, fake_client):
        fake_client.rows = [
            {"id": _ANALYSIS_ID, "user_id": _OTHER_USER_ID, "type": "stock"},
        ]

        from analyses_repository import get_for_user

        assert get_for_user(_ANALYSIS_ID, _USER_ID) is None

    def test_filters_by_user_id_and_id(self, fake_client):
        fake_client.rows = [
            {"id": _ANALYSIS_ID, "user_id": _USER_ID, "type": "stock"},
        ]

        from analyses_repository import get_for_user

        get_for_user(_ANALYSIS_ID, _USER_ID)

        assert fake_client.last_query is not None
        assert ("id", _ANALYSIS_ID) in fake_client.last_query.filters
        assert ("user_id", _USER_ID) in fake_client.last_query.filters

    def test_rejects_missing_analysis_id(self, fake_client):
        from analyses_repository import get_for_user

        with pytest.raises(ValueError, match="analysis_id is required"):
            get_for_user("", _USER_ID)
        assert fake_client.last_query is None

    def test_rejects_missing_user_id(self, fake_client):
        from analyses_repository import get_for_user

        with pytest.raises(ValueError, match="user_id is required"):
            get_for_user(_ANALYSIS_ID, "")
        assert fake_client.last_query is None


class TestDeleteForUser:
    def test_deletes_owned_row(self, fake_client):
        fake_client.rows = [
            {"id": _ANALYSIS_ID, "user_id": _USER_ID, "type": "stock"},
        ]

        from analyses_repository import delete_for_user

        assert delete_for_user(_ANALYSIS_ID, _USER_ID) is True
        assert fake_client.rows == []

    def test_returns_false_when_missing(self, fake_client):
        from analyses_repository import delete_for_user

        assert delete_for_user(_ANALYSIS_ID, _USER_ID) is False

    def test_returns_false_for_other_users_row(self, fake_client):
        fake_client.rows = [
            {"id": _ANALYSIS_ID, "user_id": _OTHER_USER_ID, "type": "stock"},
        ]

        from analyses_repository import delete_for_user

        assert delete_for_user(_ANALYSIS_ID, _USER_ID) is False
        assert len(fake_client.rows) == 1

    def test_filters_by_user_id_and_id(self, fake_client):
        fake_client.rows = [
            {"id": _ANALYSIS_ID, "user_id": _USER_ID, "type": "stock"},
        ]

        from analyses_repository import delete_for_user

        delete_for_user(_ANALYSIS_ID, _USER_ID)

        assert fake_client.last_query is not None
        assert fake_client.last_query.operation == "delete"
        assert ("id", _ANALYSIS_ID) in fake_client.last_query.filters
        assert ("user_id", _USER_ID) in fake_client.last_query.filters

    def test_rejects_missing_analysis_id(self, fake_client):
        from analyses_repository import delete_for_user

        with pytest.raises(ValueError, match="analysis_id is required"):
            delete_for_user("", _USER_ID)
        assert fake_client.last_query is None

    def test_rejects_missing_user_id(self, fake_client):
        from analyses_repository import delete_for_user

        with pytest.raises(ValueError, match="user_id is required"):
            delete_for_user(_ANALYSIS_ID, "")
        assert fake_client.last_query is None
