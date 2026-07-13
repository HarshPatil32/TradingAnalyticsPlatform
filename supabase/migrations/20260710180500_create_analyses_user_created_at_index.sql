-- 20260710180500
-- create_analyses_user_created_at_index.sql

create index analyses_user_id_created_at_idx
  on public.analyses (user_id, created_at desc);
