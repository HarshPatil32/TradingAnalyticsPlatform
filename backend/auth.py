"""Supabase JWT verification for protected Flask routes.

Apply @require_auth to routes that need a verified user_id before calling
service-role repositories (which bypass RLS).
"""

from __future__ import annotations

import functools
import logging
import os

import jwt
from flask import g, jsonify, request

_JWT_ALGORITHMS = ["HS256"]
_EXPECTED_AUDIENCE = "authenticated"

_logger = logging.getLogger(__name__)


def _extract_bearer_token(header_value: str | None) -> str | None:
    if not header_value:
        return None
    parts = header_value.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def _decode_supabase_jwt(token: str, secret: str) -> dict:
    return jwt.decode(
        token,
        secret,
        algorithms=_JWT_ALGORITHMS,
        audience=_EXPECTED_AUDIENCE,
    )


def require_auth(view_func):
    """Verify a Supabase JWT and attach g.user_id before calling the view."""

    @functools.wraps(view_func)
    def wrapper(*args, **kwargs):
        secret = os.environ.get("SUPABASE_JWT_SECRET")
        if not secret:
            _logger.warning("Auth rejected: SUPABASE_JWT_SECRET is not configured")
            return jsonify({"error": "Unauthorized"}), 401

        token = _extract_bearer_token(request.headers.get("Authorization"))
        if not token:
            return jsonify({"error": "Unauthorized"}), 401

        try:
            claims = _decode_supabase_jwt(token, secret)
        except jwt.InvalidTokenError as exc:
            _logger.warning("Auth rejected: %s", type(exc).__name__)
            return jsonify({"error": "Unauthorized"}), 401

        user_id = claims.get("sub")
        if not isinstance(user_id, str) or not user_id.strip():
            return jsonify({"error": "Unauthorized"}), 401

        g.user_id = user_id.strip()
        return view_func(*args, **kwargs)

    return wrapper
