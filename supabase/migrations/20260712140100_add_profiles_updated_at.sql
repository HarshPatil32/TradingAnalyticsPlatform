-- 20260712140100
-- add_profiles_updated_at.sql

alter table public.profiles
  add column updated_at timestamptz not null default now();

create trigger profiles_set_updated_at
  before update on public.profiles
  for each row
  execute function public.set_updated_at();
