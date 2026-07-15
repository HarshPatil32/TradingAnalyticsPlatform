-- 20260715140000
-- add_analyses_update_delete_policies.sql

create policy analyses_update_own
  on public.analyses
  for update
  to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

create policy analyses_delete_own
  on public.analyses
  for delete
  to authenticated
  using (user_id = auth.uid());

-- Full-row update/delete: analyses has no billing-controlled columns (unlike profiles).
-- If tier/plan columns are added later, scope update grants to specific columns.
grant update, delete on public.analyses to authenticated;
