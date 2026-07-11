-- 20260710180300
-- create_profiles_table.sql

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  tier text not null default 'free',
  created_at timestamptz not null default now()
);
