"""Data access for the analyses table.

All functions require the caller's user_id and filter every query by it.
The underlying client is service-role and bypasses RLS — callers must
authenticate the user and pass a trustworthy user_id before calling here.
"""

from __future__ import annotations

from typing import Any, cast

import supabase_client

_MAX_LIST_LIMIT = 200


def _require_non_empty_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def create(
    user_id: str,
    type: str,
    result: dict,
    summary_return: float | None = None,
    instrument_count: int | None = None,
) -> dict[str, Any]:
    """Insert an analysis row for user_id and return the created row."""
    user_id = _require_non_empty_str(user_id, "user_id")
    type = _require_non_empty_str(type, "type")
    if not isinstance(result, dict):
        raise ValueError("result must be a dict")

    payload: dict = {
        "user_id": user_id,
        "type": type,
        "result": result,
    }
    if summary_return is not None:
        payload["summary_return"] = summary_return
    if instrument_count is not None:
        payload["instrument_count"] = instrument_count

    client = supabase_client.get_service_role_client()
    response = client.table("analyses").insert(payload).execute()
    return cast(dict[str, Any], response.data[0])


def list_for_user(user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Return analyses for user_id, newest first."""
    user_id = _require_non_empty_str(user_id, "user_id")
    if type(limit) is not int or limit <= 0 or limit > _MAX_LIST_LIMIT:
        raise ValueError(f"limit must be a positive integer up to {_MAX_LIST_LIMIT}")

    client = supabase_client.get_service_role_client()
    response = (
        client.table("analyses")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return cast(list[dict[str, Any]], response.data)


def get_for_user(analysis_id: str, user_id: str) -> dict[str, Any] | None:
    """Return the analysis if it exists and belongs to user_id, else None.

    Returns None for both "not found" and "belongs to another user" so callers
    cannot distinguish the two cases (avoids leaking row existence across users).
    """
    analysis_id = _require_non_empty_str(analysis_id, "analysis_id")
    user_id = _require_non_empty_str(user_id, "user_id")

    client = supabase_client.get_service_role_client()
    response = (
        client.table("analyses")
        .select("*")
        .eq("id", analysis_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return cast(dict[str, Any], response.data[0])


def delete_for_user(analysis_id: str, user_id: str) -> bool:
    """Delete the analysis if it exists and belongs to user_id.

    Returns False for both "not found" and "belongs to another user" so callers
    cannot distinguish the two cases (avoids leaking row existence across users).
    """
    analysis_id = _require_non_empty_str(analysis_id, "analysis_id")
    user_id = _require_non_empty_str(user_id, "user_id")

    client = supabase_client.get_service_role_client()
    response = (
        client.table("analyses")
        .delete()
        .eq("id", analysis_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(response.data)
