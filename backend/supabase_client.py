"""Server-side Supabase client using the service-role key (bypasses RLS).

Never import or use this from a code path reachable by unauthenticated or
unvalidated input without adding authorization checks in the caller — the
service-role key bypasses Row Level Security entirely.
"""

import os
import threading

from supabase import Client, create_client

_client: Client | None = None
_client_lock = threading.Lock()


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
        _client = create_client(url, key)
        return _client
