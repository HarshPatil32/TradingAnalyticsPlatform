-- 20260710180600
-- create_usage_counters_table.sql

create table public.usage_counters (
  user_id uuid not null references auth.users (id) on delete cascade,
  period text not null check (period ~ '^\d{4}-(0[1-9]|1[0-2])$'),
  count integer not null default 0 check (count >= 0),
  primary key (user_id, period)
);
