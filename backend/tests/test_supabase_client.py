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
            "supabase_client.create_client", lambda url, key: fake_client
        )

        from supabase_client import get_service_role_client

        assert get_service_role_client() is fake_client

    def test_caches_client(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", _FAKE_URL)
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", _FAKE_KEY)

        call_count = 0

        def fake_create_client(url, key):
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
        monkeypatch.setattr("supabase_client.create_client", lambda url, key: object())

        from supabase_client import get_service_role_client

        with caplog.at_level(logging.DEBUG):
            get_service_role_client()
        for record in caplog.records:
            assert _FAKE_KEY not in record.message
