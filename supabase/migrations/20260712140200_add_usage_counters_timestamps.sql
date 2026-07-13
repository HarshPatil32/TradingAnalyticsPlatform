-- 20260712140200
-- add_usage_counters_timestamps.sql

alter table public.usage_counters
  add column created_at timestamptz not null default now(),
  add column updated_at timestamptz not null default now();

create trigger usage_counters_set_updated_at
  before update on public.usage_counters
  for each row
  execute function public.set_updated_at();
