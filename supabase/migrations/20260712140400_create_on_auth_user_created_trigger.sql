-- 20260712140400
-- create_on_auth_user_created_trigger.sql

create trigger on_auth_user_created
  after insert on auth.users
  for each row
  execute function public.handle_new_user();
