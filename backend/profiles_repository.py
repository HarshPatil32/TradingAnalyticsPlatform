"""Data access for the profiles table.

All functions require the caller's user_id.
The underlying client is service-role and bypasses RLS — callers must
authenticate the user and pass a trustworthy user_id before calling here.
"""

from __future__ import annotations

from typing import Any, cast

import supabase_client


def _require_non_empty_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def _select_profile(client, user_id: str) -> dict[str, Any] | None:
    response = supabase_client.execute_with_retry(
        lambda: client.table("profiles")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return cast(dict[str, Any], response.data[0])


def get_or_create(user_id: str) -> dict[str, Any]:
    """Return the profile for user_id, creating it with defaults if missing."""
    user_id = _require_non_empty_str(user_id, "user_id")

    client = supabase_client.get_service_role_client()
    existing = _select_profile(client, user_id)
    if existing is not None:
        return existing

    supabase_client.execute_with_retry(
        lambda: client.table("profiles")
        .upsert(
            {"id": user_id},
            on_conflict="id",
            ignore_duplicates=True,
        )
        .execute(),
        idempotent=False,
    )

    profile = _select_profile(client, user_id)
    if profile is None:
        raise RuntimeError("profile could not be resolved for user_id")
    return profile
