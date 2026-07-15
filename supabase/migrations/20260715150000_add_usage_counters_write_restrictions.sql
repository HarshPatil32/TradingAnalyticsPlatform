-- 20260715150000
-- add_usage_counters_write_restrictions.sql

-- usage_counters is intentionally read-only for authenticated users.
-- All writes go through service_role (backend), which bypasses RLS by default.
-- No insert/update/delete policies for authenticated; explicit revokes block writes.
-- TRUNCATE bypasses RLS, so revoke it even though PostgREST does not expose it.
revoke insert, update, delete, truncate on public.usage_counters from authenticated;

comment on table public.usage_counters is
  'Writes restricted to service_role; authenticated is select-only.';
