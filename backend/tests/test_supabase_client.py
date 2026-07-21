"""Tests for the server-side Supabase service-role client factory."""

import logging

import pytest

_FAKE_URL = "https://example.supabase.co"
_FAKE_KEY = "fake-service-role-key-value"


@pytest.fixture(autouse=True)
def reset_supabase_client():
    import supabase_client

    supabase_client._client = None
    yield
    supabase_client._client = None


class TestGetServiceRoleClientMissingEnv:
    def test_raises_when_url_missing(self, monkeypatch):
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", _FAKE_KEY)

        from supabase_client import get_service_role_client

        with pytest.raises(RuntimeError, match="SUPABASE_URL"):
            get_service_role_client()

    def test_raises_when_key_missing(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", _FAKE_URL)
        monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

        from supabase_client import get_service_role_client

        with pytest.raises(RuntimeError, match="SUPABASE_SERVICE_ROLE_KEY"):
            get_service_role_client()

    def test_raises_when_both_missing(self, monkeypatch):
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

        from supabase_client import get_service_role_client

        with pytest.raises(
            RuntimeError, match="SUPABASE_URL.*SUPABASE_SERVICE_ROLE_KEY"
        ):
            get_service_role_client()

    def test_error_message_does_not_include_key_value_when_url_missing(
        self, monkeypatch
    ):
        monkeypatch.setenv("SUPABASE_URL", _FAKE_URL)
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", _FAKE_KEY)
        monkeypatch.delenv("SUPABASE_URL", raising=False)

        from supabase_client import get_service_role_client

        with pytest.raises(RuntimeError) as exc_info:
            get_service_role_client()
        assert _FAKE_KEY not in str(exc_info.value)

    def test_error_message_does_not_include_key_value_when_key_missing(
        self, monkeypatch
    ):
        monkeypatch.setenv("SUPABASE_URL", _FAKE_URL)
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", _FAKE_KEY)
        monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

        from supabase_client import get_service_role_client

        with pytest.raises(RuntimeError) as exc_info:
            get_service_role_client()
        assert _FAKE_KEY not in str(exc_info.value)


class TestGetServiceRoleClientSuccess:
    def test_returns_client_when_env_set(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", _FAKE_URL)
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", _FAKE_KEY)

        fake_client = object()
        monkeypatch.setattr(
            "supabase_client.create_client",
            lambda url, key, options=None: fake_client,
        )

        from supabase_client import get_service_role_client

        assert get_service_role_client() is fake_client

    def test_caches_client(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", _FAKE_URL)
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", _FAKE_KEY)

        call_count = 0

        def fake_create_client(url, key, options=None):
            nonlocal call_count
            call_count += 1
            return object()

        monkeypatch.setattr("supabase_client.create_client", fake_create_client)

        from supabase_client import get_service_role_client

        first = get_service_role_client()
        second = get_service_role_client()
        assert first is second
        assert call_count == 1

    def test_key_value_not_logged(self, monkeypatch, caplog):
        monkeypatch.setenv("SUPABASE_URL", _FAKE_URL)
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", _FAKE_KEY)
        monkeypatch.setattr(
            "supabase_client.create_client",
            lambda url, key, options=None: object(),
        )

        from supabase_client import get_service_role_client

        with caplog.at_level(logging.DEBUG):
            get_service_role_client()
        for record in caplog.records:
            assert _FAKE_KEY not in record.message


class TestCheckConnection:
    def test_not_configured_when_env_missing(self, monkeypatch, caplog):
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

        from supabase_client import check_connection

        with caplog.at_level(logging.WARNING):
            result = check_connection()
        assert result == {"configured": False, "connected": False}
        assert not caplog.records

    def test_not_configured_when_url_invalid(self, monkeypatch, caplog):
        monkeypatch.setenv("SUPABASE_URL", "not-a-valid-url")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", _FAKE_KEY)

        from supabase_client import check_connection

        with caplog.at_level(logging.WARNING):
            result = check_connection()
        assert result == {"configured": False, "connected": False}
        assert not caplog.records

    def test_connected_when_query_succeeds(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", _FAKE_URL)
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", _FAKE_KEY)

        class FakeQuery:
            def limit(self, n):
                return self

            def execute(self):
                return object()

        class FakeTable:
            def select(self, cols):
                return FakeQuery()

        class FakeClient:
            def table(self, name):
                assert name == "profiles"
                return FakeTable()

        monkeypatch.setattr(
            "supabase_client.create_client",
            lambda url, key, options=None: FakeClient(),
        )

        from supabase_client import check_connection

        assert check_connection() == {"configured": True, "connected": True}

    def test_not_connected_when_query_raises(self, monkeypatch, caplog):
        monkeypatch.setenv("SUPABASE_URL", _FAKE_URL)
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", _FAKE_KEY)

        class FakeQuery:
            def limit(self, n):
                return self

            def execute(self):
                raise ConnectionError("secret-url-and-key-info")

        class FakeTable:
            def select(self, cols):
                return FakeQuery()

        class FakeClient:
            def table(self, name):
                return FakeTable()

        monkeypatch.setattr(
            "supabase_client.create_client",
            lambda url, key, options=None: FakeClient(),
        )

        from supabase_client import check_connection

        with caplog.at_level(logging.WARNING):
            result = check_connection()
        assert result == {"configured": True, "connected": False}
        assert any("ConnectionError" in r.message for r in caplog.records)
        for record in caplog.records:
            assert _FAKE_KEY not in record.message
            assert "secret-url-and-key-info" not in record.message


class TestExecuteWithRetry:
    def test_succeeds_without_retry(self):
        from supabase_client import execute_with_retry

        assert execute_with_retry(lambda: "ok") == "ok"

    def test_retries_connect_error_then_succeeds(self, monkeypatch):
        import httpx

        from supabase_client import execute_with_retry

        attempts = 0
        sleeps: list[float] = []
        monkeypatch.setattr("supabase_client.time.sleep", lambda s: sleeps.append(s))

        def flaky():
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise httpx.ConnectError("network down")
            return "ok"

        assert execute_with_retry(flaky, retries=2) == "ok"
        assert attempts == 2
        assert sleeps == [0.3]

    def test_retries_read_timeout_when_idempotent(self, monkeypatch):
        import httpx

        from supabase_client import execute_with_retry

        attempts = 0
        monkeypatch.setattr("supabase_client.time.sleep", lambda _s: None)

        def flaky():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise httpx.ReadTimeout("slow")
            return "ok"

        assert execute_with_retry(flaky, retries=2, idempotent=True) == "ok"
        assert attempts == 3

    def test_does_not_retry_read_timeout_when_not_idempotent(self, monkeypatch):
        import httpx

        from supabase_client import execute_with_retry

        attempts = 0
        monkeypatch.setattr("supabase_client.time.sleep", lambda _s: None)

        def flaky():
            nonlocal attempts
            attempts += 1
            raise httpx.ReadTimeout("slow")

        with pytest.raises(httpx.ReadTimeout):
            execute_with_retry(flaky, retries=2, idempotent=False)
        assert attempts == 1

    def test_raises_after_exhausting_retries(self, monkeypatch):
        import httpx

        from supabase_client import execute_with_retry

        attempts = 0
        monkeypatch.setattr("supabase_client.time.sleep", lambda _s: None)

        def always_fails():
            nonlocal attempts
            attempts += 1
            raise httpx.ConnectError("network down")

        with pytest.raises(httpx.ConnectError):
            execute_with_retry(always_fails, retries=2)
        assert attempts == 3

    def test_does_not_retry_api_error(self, monkeypatch):
        from postgrest.exceptions import APIError

        from supabase_client import execute_with_retry

        attempts = 0
        monkeypatch.setattr("supabase_client.time.sleep", lambda _s: None)

        def api_failure():
            nonlocal attempts
            attempts += 1
            raise APIError({"message": "constraint violation"})

        with pytest.raises(APIError):
            execute_with_retry(api_failure, retries=2)
        assert attempts == 1


class TestClientTimeout:
    def test_passes_default_timeout_to_client_options(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", _FAKE_URL)
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", _FAKE_KEY)
        monkeypatch.delenv("SUPABASE_DB_TIMEOUT_SECONDS", raising=False)

        captured: dict = {}

        def fake_create_client(url, key, options=None):
            captured["options"] = options
            return object()

        monkeypatch.setattr("supabase_client.create_client", fake_create_client)

        from supabase_client import get_service_role_client

        get_service_role_client()
        assert captured["options"].postgrest_client_timeout == 10

    def test_reads_timeout_from_env(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", _FAKE_URL)
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", _FAKE_KEY)
        monkeypatch.setenv("SUPABASE_DB_TIMEOUT_SECONDS", "15")

        captured: dict = {}

        def fake_create_client(url, key, options=None):
            captured["options"] = options
            return object()

        monkeypatch.setattr("supabase_client.create_client", fake_create_client)

        from supabase_client import get_service_role_client

        get_service_role_client()
        assert captured["options"].postgrest_client_timeout == 15.0

    @pytest.mark.parametrize(
        "timeout_value",
        ["abc", "-1", "0"],
    )
    def test_falls_back_to_default_for_invalid_timeout_env(
        self, monkeypatch, timeout_value
    ):
        monkeypatch.setenv("SUPABASE_URL", _FAKE_URL)
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", _FAKE_KEY)
        monkeypatch.setenv("SUPABASE_DB_TIMEOUT_SECONDS", timeout_value)

        captured: dict = {}

        def fake_create_client(url, key, options=None):
            captured["options"] = options
            return object()

        monkeypatch.setattr("supabase_client.create_client", fake_create_client)

        from supabase_client import get_service_role_client

        get_service_role_client()
        assert captured["options"].postgrest_client_timeout == 10
