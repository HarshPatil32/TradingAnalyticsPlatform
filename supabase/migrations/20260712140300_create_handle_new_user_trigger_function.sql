-- 20260712140300
-- create_handle_new_user_trigger_function.sql

-- SECURITY DEFINER: runs as the function owner so it can insert into public.profiles
-- when auth.users is created. This bypasses RLS (intentional once RLS is enabled).
create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id)
  values (new.id)
  on conflict (id) do nothing;
  return new;
end;
$$;
