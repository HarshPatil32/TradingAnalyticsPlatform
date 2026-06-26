"""Tests for env var validation (validate_env_vars + health check endpoint)."""
import pytest
from unittest.mock import patch


class TestValidateEnvVarsShape:
    def test_returns_expected_keys(self):
        from app import validate_env_vars
        result = validate_env_vars()
        assert set(result.keys()) == {"missing_required", "missing_optional", "all_present"}

    def test_missing_required_is_list(self):
        from app import validate_env_vars
        result = validate_env_vars()
        assert isinstance(result["missing_required"], list)

    def test_all_present_is_bool(self):
        from app import validate_env_vars
        result = validate_env_vars()
        assert isinstance(result["all_present"], bool)


class TestValidateEnvVarsLogic:
    def test_all_present_true_when_no_required_vars_missing(self, monkeypatch):
        # All current manifest vars are optional, so all_present should always be True
        from app import validate_env_vars
        result = validate_env_vars()
        assert result["all_present"] is True
        assert result["missing_required"] == []

    def test_optional_var_reported_when_unset(self, monkeypatch):
        monkeypatch.delenv("PORT", raising=False)
        monkeypatch.delenv("FLASK_DEBUG", raising=False)
        from app import validate_env_vars
        result = validate_env_vars()
        assert "PORT" in result["missing_optional"]

    def test_optional_var_not_reported_when_set(self, monkeypatch):
        monkeypatch.setenv("PORT", "5001")
        from app import validate_env_vars
        result = validate_env_vars()
        assert "PORT" not in result["missing_optional"]

    def test_required_var_triggers_all_present_false(self, monkeypatch):
        # Temporarily inject a required var into the manifest to test the path
        import app as app_module
        original = app_module._ENV_VAR_MANIFEST
        app_module._ENV_VAR_MANIFEST = (
            {"name": "FAKE_REQUIRED_VAR", "required": True, "description": "test only"},
        )
        monkeypatch.delenv("FAKE_REQUIRED_VAR", raising=False)
        try:
            result = app_module.validate_env_vars()
            assert result["all_present"] is False
            assert "FAKE_REQUIRED_VAR" in result["missing_required"]
        finally:
            app_module._ENV_VAR_MANIFEST = original

    def test_no_secret_values_in_log_output(self, monkeypatch, caplog):
        monkeypatch.setenv("PORT", "supersecret")
        import logging
        from app import validate_env_vars
        with caplog.at_level(logging.INFO):
            validate_env_vars()
        for record in caplog.records:
            assert "supersecret" not in record.message


class TestAllowedOriginsParsing:
    def test_var_unset_returns_wildcard(self, monkeypatch):
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
        from app import _parse_allowed_origins
        assert _parse_allowed_origins() == "*"

    def test_explicit_wildcard_returns_string(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGINS", "*")
        from app import _parse_allowed_origins
        assert _parse_allowed_origins() == "*"

    def test_single_origin(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGINS", "https://mytradingbot.vercel.app")
        from app import _parse_allowed_origins
        assert _parse_allowed_origins() == ["https://mytradingbot.vercel.app"]

    def test_multiple_origins_comma_separated(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGINS", "https://foo.com,https://bar.com")
        from app import _parse_allowed_origins
        assert _parse_allowed_origins() == ["https://foo.com", "https://bar.com"]

    def test_whitespace_around_origins_is_stripped(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGINS", "  https://foo.com , https://bar.com  ")
        from app import _parse_allowed_origins
        assert _parse_allowed_origins() == ["https://foo.com", "https://bar.com"]

    def test_trailing_comma_ignored(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGINS", "https://foo.com,")
        from app import _parse_allowed_origins
        assert _parse_allowed_origins() == ["https://foo.com"]

    def test_empty_string_falls_back_to_wildcard(self, monkeypatch, caplog):
        monkeypatch.setenv("ALLOWED_ORIGINS", "")
        import logging
        from app import _parse_allowed_origins
        with caplog.at_level(logging.WARNING):
            result = _parse_allowed_origins()
        assert result == "*"
        assert any("empty" in r.message for r in caplog.records)

    def test_whitespace_only_falls_back_to_wildcard(self, monkeypatch, caplog):
        monkeypatch.setenv("ALLOWED_ORIGINS", "   ")
        import logging
        from app import _parse_allowed_origins
        with caplog.at_level(logging.WARNING):
            result = _parse_allowed_origins()
        assert result == "*"
        assert any("empty" in r.message for r in caplog.records)

    def test_invalid_scheme_logs_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("ALLOWED_ORIGINS", "not-a-url,https://good.com")
        import logging
        from app import _parse_allowed_origins
        with caplog.at_level(logging.WARNING):
            result = _parse_allowed_origins()
        assert result == ["not-a-url", "https://good.com"]
        assert any("not-a-url" in r.message for r in caplog.records)

    def test_valid_origins_no_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("ALLOWED_ORIGINS", "https://foo.com,http://localhost:3000")
        import logging
        from app import _parse_allowed_origins
        with caplog.at_level(logging.WARNING):
            result = _parse_allowed_origins()
        assert result == ["https://foo.com", "http://localhost:3000"]
        assert not caplog.records

    def test_allowed_origins_in_manifest(self, monkeypatch):
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
        from app import validate_env_vars
        result = validate_env_vars()
        assert "ALLOWED_ORIGINS" in result["missing_optional"]

    def test_allowed_origins_not_in_missing_when_set(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGINS", "https://foo.com")
        from app import validate_env_vars
        result = validate_env_vars()
        assert "ALLOWED_ORIGINS" not in result["missing_optional"]


class TestBuildCorsOrigins:
    def test_wildcard_passthrough(self):
        from app import _build_cors_origins
        assert _build_cors_origins("*") == "*"

    def test_vercel_production_adds_preview_regex(self):
        from app import _build_cors_origins
        result = _build_cors_origins(["https://optimized-macd-proj.vercel.app"])
        assert result[0] == "https://optimized-macd-proj.vercel.app"
        preview_pattern = result[1]
        assert preview_pattern.search(
            "https://optimized-macd-proj-fbg5rpn4p-harsh-patils-projects-b8fb0f7c.vercel.app"
        )
        assert preview_pattern.search("https://optimized-macd-proj.vercel.app")
        assert not preview_pattern.search("https://other-project.vercel.app")

    def test_explicit_wildcard_pattern(self):
        from app import _build_cors_origins
        result = _build_cors_origins(["https://*.vercel.app"])
        pattern = result[1]
        assert pattern.search("https://optimized-macd-proj.vercel.app")
        assert pattern.search(
            "https://optimized-macd-proj-fbg5rpn4p-harsh-patils-projects-b8fb0f7c.vercel.app"
        )


class TestHealthCheckEnvStatus:
    @pytest.fixture(scope="class")
    def client(self):
        from app import app as flask_app
        flask_app.config["TESTING"] = True
        with flask_app.test_client() as c:
            yield c

    def test_env_status_present_in_response(self, client):
        resp = client.get("/")
        data = resp.get_json()
        assert "env_status" in data

    def test_env_status_has_all_present_field(self, client):
        resp = client.get("/")
        data = resp.get_json()
        assert "all_present" in data["env_status"]

    def test_env_status_has_missing_required_field(self, client):
        resp = client.get("/")
        data = resp.get_json()
        assert "missing_required" in data["env_status"]

    def test_missing_required_is_list(self, client):
        resp = client.get("/")
        data = resp.get_json()
        assert isinstance(data["env_status"]["missing_required"], list)
