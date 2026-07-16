-- 20260715160000
-- revoke_anon_privileges_on_user_tables.sql

-- anon (unauthenticated PostgREST requests using the anon/public API key) must have
-- zero access to user data tables. RLS policies already only grant to authenticated,
-- but table-level GRANTs are separate from RLS and Supabase projects can pick up broad
-- default privileges for anon outside of migration history. Make the deny explicit.
revoke all on public.profiles from anon;
revoke all on public.analyses from anon;
revoke all on public.usage_counters from anon;

comment on table public.profiles is
  'anon has no privileges; access is authenticated-only via RLS, service_role bypasses RLS.';
comment on table public.analyses is
  'anon has no privileges; access is authenticated-only via RLS, service_role bypasses RLS.';
comment on table public.usage_counters is
  'anon has no privileges; writes restricted to service_role, select-only for authenticated via RLS.';
