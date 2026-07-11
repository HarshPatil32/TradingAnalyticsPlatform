-- 20260710180400
-- create_analyses_table.sql

create table public.analyses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  type text not null,
  result jsonb not null,
  summary_return numeric,
  instrument_count integer check (instrument_count >= 0),
  created_at timestamptz not null default now()
);
