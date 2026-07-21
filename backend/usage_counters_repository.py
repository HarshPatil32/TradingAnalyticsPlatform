"""Data access for the usage_counters table.

All functions require the caller's user_id and filter every query by it.
The underlying client is service-role and bypasses RLS — callers must
authenticate the user and pass a trustworthy user_id before calling here.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, cast

import supabase_client

_PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _require_non_empty_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def _resolve_period(period: str | None) -> str:
    if period is None:
        return datetime.now(timezone.utc).strftime("%Y-%m")
    period = _require_non_empty_str(period, "period")
    if not _PERIOD_RE.match(period):
        raise ValueError("period must be in YYYY-MM format")
    return period


def increment(user_id: str, period: str | None = None) -> dict[str, Any]:
    """Atomically increment the counter for user_id/period, creating it if needed."""
    user_id = _require_non_empty_str(user_id, "user_id")
    period = _resolve_period(period)

    client = supabase_client.get_service_role_client()
    response = client.rpc(
        "increment_usage_counter", {"p_user_id": user_id, "p_period": period}
    ).execute()
    rows = cast(list[dict[str, Any]], response.data)
    return rows[0]


def read(user_id: str, period: str | None = None) -> int:
    """Return the current count for user_id/period, or 0 if no row exists."""
    user_id = _require_non_empty_str(user_id, "user_id")
    period = _resolve_period(period)

    client = supabase_client.get_service_role_client()
    response = (
        client.table("usage_counters")
        .select("count")
        .eq("user_id", user_id)
        .eq("period", period)
        .limit(1)
        .execute()
    )
    if not response.data:
        return 0
    rows = cast(list[dict[str, Any]], response.data)
    return cast(int, rows[0]["count"])
