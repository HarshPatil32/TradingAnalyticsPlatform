-- 20260716100000
-- create_increment_usage_counter_function.sql

create function public.increment_usage_counter(p_user_id uuid, p_period text)
returns setof public.usage_counters
language sql
set search_path = ''
as $$
  insert into public.usage_counters (user_id, period, count)
  values (p_user_id, p_period, 1)
  on conflict (user_id, period)
  do update set count = public.usage_counters.count + 1
  returning *;
$$;

revoke all on function public.increment_usage_counter(uuid, text) from public;
grant execute on function public.increment_usage_counter(uuid, text) to service_role;
