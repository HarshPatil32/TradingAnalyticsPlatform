-- 20260715100000
-- enable_rls_on_user_tables.sql

-- Use enable (not force) so table owners and SECURITY DEFINER functions
-- (e.g. handle_new_user) can still insert into profiles on signup.
alter table public.profiles enable row level security;
alter table public.analyses enable row level security;
alter table public.usage_counters enable row level security;

create policy profiles_select_own
  on public.profiles
  for select
  to authenticated
  using (id = auth.uid());

create policy analyses_select_own
  on public.analyses
  for select
  to authenticated
  using (user_id = auth.uid());

create policy analyses_insert_own
  on public.analyses
  for insert
  to authenticated
  with check (user_id = auth.uid());

create policy usage_counters_select_own
  on public.usage_counters
  for select
  to authenticated
  using (user_id = auth.uid());

grant select on public.profiles to authenticated;
grant select, insert on public.analyses to authenticated;
grant select on public.usage_counters to authenticated;
