"""Supabase JWT verification for Flask routes.

Apply @require_auth to routes that need a verified user_id before calling
service-role repositories (which bypass RLS).

Apply @optional_auth to routes usable while logged out; they receive g.user_id
when a valid Supabase JWT is present, otherwise g.user_id is None.
"""

from __future__ import annotations

import functools
import logging
import os
from typing import Any

import jwt
from flask import g, jsonify, request

_JWT_ALGORITHMS = ["HS256"]
_EXPECTED_AUDIENCE = "authenticated"
_WWW_AUTHENTICATE = 'Bearer realm="api"'

_logger = logging.getLogger(__name__)


def _extract_bearer_token(header_value: str | None) -> str | None:
    if not header_value:
        return None
    parts = header_value.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def _decode_supabase_jwt(token: str, secret: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        secret,
        algorithms=_JWT_ALGORITHMS,
        audience=_EXPECTED_AUDIENCE,
    )


def _unauthorized():
    response = jsonify({"error": "Unauthorized"})
    response.headers["WWW-Authenticate"] = _WWW_AUTHENTICATE
    return response, 401


def require_auth(view_func):
    """Verify a Supabase JWT and attach g.user_id before calling the view."""

    @functools.wraps(view_func)
    def wrapper(*args, **kwargs):
        secret = os.environ.get("SUPABASE_JWT_SECRET")
        if not secret:
            _logger.warning("Auth rejected: SUPABASE_JWT_SECRET is not configured")
            return _unauthorized()

        token = _extract_bearer_token(request.headers.get("Authorization"))
        if not token:
            return _unauthorized()

        try:
            claims = _decode_supabase_jwt(token, secret)
        except jwt.InvalidTokenError as exc:
            _logger.warning("Auth rejected: %s", type(exc).__name__)
            return _unauthorized()

        user_id = claims.get("sub")
        if not isinstance(user_id, str) or not user_id.strip():
            return _unauthorized()

        g.user_id = user_id.strip()
        return view_func(*args, **kwargs)

    return wrapper


def optional_auth(view_func):
    """Attach g.user_id when a valid Supabase JWT is present; otherwise None."""

    @functools.wraps(view_func)
    def wrapper(*args, **kwargs):
        g.user_id = None

        secret = os.environ.get("SUPABASE_JWT_SECRET")
        if not secret:
            _logger.info("Optional auth skipped: SUPABASE_JWT_SECRET is not configured")
            return view_func(*args, **kwargs)

        token = _extract_bearer_token(request.headers.get("Authorization"))
        if not token:
            return view_func(*args, **kwargs)

        try:
            claims = _decode_supabase_jwt(token, secret)
        except jwt.InvalidTokenError as exc:
            _logger.warning("Optional auth ignored: %s", type(exc).__name__)
            return view_func(*args, **kwargs)

        user_id = claims.get("sub")
        if isinstance(user_id, str) and user_id.strip():
            g.user_id = user_id.strip()

        return view_func(*args, **kwargs)

    return wrapper
