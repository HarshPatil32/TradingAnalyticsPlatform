"""Tests for Supabase JWT verification (require_auth and optional_auth)."""

import logging
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from flask import Flask, g, jsonify

_FAKE_SECRET = "fake-jwt-secret-value-padded-here"
_OTHER_SECRET = "different-secret-value-padded-here"
_DEFAULT_SUB = "user-123"
_WWW_AUTHENTICATE = 'Bearer realm="api"'


def _assert_unauthorized(response):
    assert response.status_code == 401
    assert response.get_json() == {"error": "Unauthorized"}
    assert response.headers.get("WWW-Authenticate") == _WWW_AUTHENTICATE


def _make_token(
    secret: str = _FAKE_SECRET,
    sub: str = _DEFAULT_SUB,
    **overrides,
) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": sub,
        "aud": "authenticated",
        "exp": now + timedelta(hours=1),
        "iat": now,
    }
    claims.update(overrides)
    return jwt.encode(claims, secret, algorithm="HS256")


@pytest.fixture
def protected_client(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", _FAKE_SECRET)

    from auth import require_auth

    app = Flask(__name__)

    @app.route("/protected")
    @require_auth
    def protected():
        return jsonify({"user_id": g.user_id})

    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def optional_client(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", _FAKE_SECRET)

    from auth import optional_auth

    app = Flask(__name__)

    @app.route("/optional")
    @optional_auth
    def optional():
        return jsonify({"user_id": g.user_id})

    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def _assert_optional_anonymous(response):
    assert response.status_code == 200
    assert response.get_json() == {"user_id": None}


class TestRequireAuthSuccess:
    def test_valid_token_attaches_user_id(self, protected_client):
        token = _make_token()
        response = protected_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.get_json() == {"user_id": _DEFAULT_SUB}


class TestRequireAuthFailure:
    def test_missing_authorization_header(self, protected_client):
        response = protected_client.get("/protected")
        _assert_unauthorized(response)

    def test_malformed_authorization_header(self, protected_client):
        response = protected_client.get(
            "/protected",
            headers={"Authorization": "Token abc"},
        )
        _assert_unauthorized(response)

    def test_empty_bearer_token(self, protected_client):
        response = protected_client.get(
            "/protected",
            headers={"Authorization": "Bearer "},
        )
        _assert_unauthorized(response)

    def test_expired_token(self, protected_client):
        now = datetime.now(timezone.utc)
        token = _make_token(
            exp=now - timedelta(minutes=1),
            iat=now - timedelta(hours=1),
        )
        response = protected_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        _assert_unauthorized(response)

    def test_wrong_signature(self, protected_client):
        token = _make_token(secret=_OTHER_SECRET)
        response = protected_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        _assert_unauthorized(response)

    def test_wrong_algorithm(self, protected_client):
        now = datetime.now(timezone.utc)
        claims = {
            "sub": _DEFAULT_SUB,
            "aud": "authenticated",
            "exp": now + timedelta(hours=1),
            "iat": now,
        }
        token = jwt.encode(claims, _FAKE_SECRET, algorithm="HS384")
        response = protected_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        _assert_unauthorized(response)

    def test_wrong_audience(self, protected_client):
        token = _make_token(aud="service_role")
        response = protected_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        _assert_unauthorized(response)

    def test_empty_sub_claim(self, protected_client):
        token = _make_token(sub="")
        response = protected_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        _assert_unauthorized(response)

    def test_absent_sub_claim(self, protected_client):
        now = datetime.now(timezone.utc)
        claims = {
            "aud": "authenticated",
            "exp": now + timedelta(hours=1),
            "iat": now,
        }
        token = jwt.encode(claims, _FAKE_SECRET, algorithm="HS256")
        response = protected_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        _assert_unauthorized(response)

    def test_missing_jwt_secret(self, protected_client, monkeypatch):
        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        token = _make_token()
        response = protected_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        _assert_unauthorized(response)


class TestRequireAuthLogging:
    def test_token_and_secret_not_logged(self, protected_client, caplog):
        token = _make_token(secret=_OTHER_SECRET)
        with caplog.at_level(logging.WARNING):
            protected_client.get(
                "/protected",
                headers={"Authorization": f"Bearer {token}"},
            )
        for record in caplog.records:
            assert token not in record.message
            assert _FAKE_SECRET not in record.message
            assert _OTHER_SECRET not in record.message


class TestOptionalAuthSuccess:
    def test_valid_token_attaches_user_id(self, optional_client):
        token = _make_token()
        response = optional_client.get(
            "/optional",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.get_json() == {"user_id": _DEFAULT_SUB}


class TestOptionalAuthAnonymous:
    def test_missing_authorization_header(self, optional_client):
        response = optional_client.get("/optional")
        _assert_optional_anonymous(response)

    def test_malformed_authorization_header(self, optional_client):
        response = optional_client.get(
            "/optional",
            headers={"Authorization": "Token abc"},
        )
        _assert_optional_anonymous(response)

    def test_empty_bearer_token(self, optional_client):
        response = optional_client.get(
            "/optional",
            headers={"Authorization": "Bearer "},
        )
        _assert_optional_anonymous(response)

    def test_expired_token(self, optional_client):
        now = datetime.now(timezone.utc)
        token = _make_token(
            exp=now - timedelta(minutes=1),
            iat=now - timedelta(hours=1),
        )
        response = optional_client.get(
            "/optional",
            headers={"Authorization": f"Bearer {token}"},
        )
        _assert_optional_anonymous(response)

    def test_wrong_signature(self, optional_client):
        token = _make_token(secret=_OTHER_SECRET)
        response = optional_client.get(
            "/optional",
            headers={"Authorization": f"Bearer {token}"},
        )
        _assert_optional_anonymous(response)

    def test_wrong_algorithm(self, optional_client):
        now = datetime.now(timezone.utc)
        claims = {
            "sub": _DEFAULT_SUB,
            "aud": "authenticated",
            "exp": now + timedelta(hours=1),
            "iat": now,
        }
        token = jwt.encode(claims, _FAKE_SECRET, algorithm="HS384")
        response = optional_client.get(
            "/optional",
            headers={"Authorization": f"Bearer {token}"},
        )
        _assert_optional_anonymous(response)

    def test_wrong_audience(self, optional_client):
        token = _make_token(aud="service_role")
        response = optional_client.get(
            "/optional",
            headers={"Authorization": f"Bearer {token}"},
        )
        _assert_optional_anonymous(response)

    def test_empty_sub_claim(self, optional_client):
        token = _make_token(sub="")
        response = optional_client.get(
            "/optional",
            headers={"Authorization": f"Bearer {token}"},
        )
        _assert_optional_anonymous(response)

    def test_absent_sub_claim(self, optional_client):
        now = datetime.now(timezone.utc)
        claims = {
            "aud": "authenticated",
            "exp": now + timedelta(hours=1),
            "iat": now,
        }
        token = jwt.encode(claims, _FAKE_SECRET, algorithm="HS256")
        response = optional_client.get(
            "/optional",
            headers={"Authorization": f"Bearer {token}"},
        )
        _assert_optional_anonymous(response)

    def test_missing_jwt_secret(self, optional_client, monkeypatch):
        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        token = _make_token()
        response = optional_client.get(
            "/optional",
            headers={"Authorization": f"Bearer {token}"},
        )
        _assert_optional_anonymous(response)


class TestOptionalAuthLogging:
    def test_token_and_secret_not_logged(self, optional_client, caplog):
        token = _make_token(secret=_OTHER_SECRET)
        with caplog.at_level(logging.WARNING):
            optional_client.get(
                "/optional",
                headers={"Authorization": f"Bearer {token}"},
            )
        for record in caplog.records:
            assert token not in record.message
            assert _FAKE_SECRET not in record.message
            assert _OTHER_SECRET not in record.message

    def test_missing_jwt_secret_logged_at_info(
        self, optional_client, monkeypatch, caplog
    ):
        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        token = _make_token()
        with caplog.at_level(logging.INFO):
            response = optional_client.get(
                "/optional",
                headers={"Authorization": f"Bearer {token}"},
            )
        _assert_optional_anonymous(response)
        assert any(
            "Optional auth skipped: SUPABASE_JWT_SECRET is not configured"
            in record.message
            for record in caplog.records
        )
        for record in caplog.records:
            assert token not in record.message
            assert _FAKE_SECRET not in record.message
