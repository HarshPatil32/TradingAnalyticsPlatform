"""Server-side Supabase client using the service-role key (bypasses RLS).

Never import or use this from a code path reachable by unauthenticated or
unvalidated input without adding authorization checks in the caller — the
service-role key bypasses Row Level Security entirely.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from typing import TypeVar

import httpx
from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

_client: Client | None = None
_client_lock = threading.Lock()

_DEFAULT_DB_TIMEOUT_SECONDS = 10
_DEFAULT_RETRIES = 2
_DEFAULT_BASE_DELAY_SECONDS = 0.3

_TRANSIENT_ALWAYS = (httpx.ConnectError, httpx.ConnectTimeout)
_TRANSIENT_IF_IDEMPOTENT = (httpx.ReadTimeout, httpx.PoolTimeout)

T = TypeVar("T")


def _get_db_timeout_seconds() -> float:
    raw = os.environ.get("SUPABASE_DB_TIMEOUT_SECONDS")
    if raw is None:
        return _DEFAULT_DB_TIMEOUT_SECONDS
    try:
        timeout = float(raw)
    except ValueError:
        return _DEFAULT_DB_TIMEOUT_SECONDS
    if timeout <= 0:
        return _DEFAULT_DB_TIMEOUT_SECONDS
    return timeout


def execute_with_retry(
    execute_fn: Callable[[], T],
    *,
    idempotent: bool = True,
    retries: int = _DEFAULT_RETRIES,
    base_delay_seconds: float = _DEFAULT_BASE_DELAY_SECONDS,
) -> T:
    """Run a Supabase query with bounded retries on transient network errors.

    Non-idempotent writes (insert/RPC) only retry connection-level failures.
    Read timeouts may mean the request reached the server, so they are retried
    only when idempotent=True (reads/deletes).
    """
    retryable: tuple[type[Exception], ...] = _TRANSIENT_ALWAYS
    if idempotent:
        retryable = retryable + _TRANSIENT_IF_IDEMPOTENT

    attempt = 0
    while True:
        try:
            return execute_fn()
        except retryable:
            if attempt >= retries:
                raise
            time.sleep(base_delay_seconds * (2**attempt))
            attempt += 1


def get_service_role_client() -> Client:
    """Return a cached Supabase client authenticated with the service-role key.

    Raises RuntimeError if SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY are unset.
    Never logs or includes the key value in any exception message.
    """
    global _client
    if _client is not None:
        return _client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    missing = [
        name
        for name, value in (("SUPABASE_URL", url), ("SUPABASE_SERVICE_ROLE_KEY", key))
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Cannot create Supabase service-role client: "
            f"missing env var(s): {', '.join(missing)}"
        )

    with _client_lock:
        if _client is not None:
            return _client
        assert url and key
        options = SyncClientOptions(postgrest_client_timeout=_get_db_timeout_seconds())
        _client = create_client(url, key, options=options)
        return _client


def check_connection() -> dict[str, bool]:
    """Attempt a lightweight Supabase connection check at boot.

    Returns {"configured": bool, "connected": bool}. Never raises,
    never logs exception text (only the exception's class name) to
    avoid leaking secret-bearing error messages.
    """
    try:
        client = get_service_role_client()
    except Exception:
        return {"configured": False, "connected": False}

    try:
        execute_with_retry(
            lambda: client.table("profiles").select("id").limit(1).execute()
        )
    except Exception as exc:
        logging.warning("Supabase connection check failed: %s", type(exc).__name__)
        return {"configured": True, "connected": False}

    return {"configured": True, "connected": True}
