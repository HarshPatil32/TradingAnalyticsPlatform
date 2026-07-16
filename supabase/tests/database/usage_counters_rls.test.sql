begin;

select plan(9);

insert into auth.users (
  instance_id,
  id,
  aud,
  role,
  email,
  encrypted_password,
  email_confirmed_at,
  raw_app_meta_data,
  raw_user_meta_data,
  created_at,
  updated_at,
  confirmation_token,
  email_change,
  email_change_token_new,
  recovery_token
)
values
  (
    '00000000-0000-0000-0000-000000000000',
    'a1000000-0000-0000-0000-000000000021',
    'authenticated',
    'authenticated',
    'rls-usage-owner@example.com',
    crypt('testpassword', gen_salt('bf')),
    now(),
    '{"provider": "email", "providers": ["email"]}'::jsonb,
    '{}'::jsonb,
    now(),
    now(),
    '',
    '',
    '',
    ''
  ),
  (
    '00000000-0000-0000-0000-000000000000',
    'a1000000-0000-0000-0000-000000000022',
    'authenticated',
    'authenticated',
    'rls-usage-other@example.com',
    crypt('testpassword', gen_salt('bf')),
    now(),
    '{"provider": "email", "providers": ["email"]}'::jsonb,
    '{}'::jsonb,
    now(),
    now(),
    '',
    '',
    '',
    ''
  )
on conflict do nothing;

insert into public.usage_counters (user_id, period, count)
values
  ('a1000000-0000-0000-0000-000000000021', '2026-07', 3),
  ('a1000000-0000-0000-0000-000000000022', '2026-07', 5);

-- owner (read-only for authenticated)
set local role authenticated;
set local request.jwt.claims = '{"sub": "a1000000-0000-0000-0000-000000000021"}';

select results_eq(
  $$
    select count(*)::int
    from public.usage_counters
    where user_id = 'a1000000-0000-0000-0000-000000000021'
  $$,
  ARRAY[1],
  'owner can select own usage counter'
);

select throws_ok(
  $$
    insert into public.usage_counters (user_id, period, count)
    values ('a1000000-0000-0000-0000-000000000021', '2026-08', 1)
  $$,
  '42501',
  null,
  'authenticated cannot insert usage_counters'
);

select throws_ok(
  $$
    update public.usage_counters
    set count = 99
    where user_id = 'a1000000-0000-0000-0000-000000000021'
  $$,
  '42501',
  null,
  'authenticated cannot update usage_counters'
);

select throws_ok(
  $$
    delete from public.usage_counters
    where user_id = 'a1000000-0000-0000-0000-000000000021'
  $$,
  '42501',
  null,
  'authenticated cannot delete usage_counters'
);

-- other user
reset role;
set local role authenticated;
set local request.jwt.claims = '{"sub": "a1000000-0000-0000-0000-000000000022"}';

select results_eq(
  $$
    select count(*)::int
    from public.usage_counters
    where user_id = 'a1000000-0000-0000-0000-000000000021'
  $$,
  ARRAY[0],
  'other user cannot select owner usage counter'
);

-- anon
reset role;
set local request.jwt.claims = '{}';
set local role anon;

select throws_ok(
  'select * from public.usage_counters',
  '42501',
  null,
  'anon cannot select usage_counters'
);

select throws_ok(
  $$
    insert into public.usage_counters (user_id, period, count)
    values ('a1000000-0000-0000-0000-000000000021', '2026-08', 1)
  $$,
  '42501',
  null,
  'anon cannot insert usage_counters'
);

select throws_ok(
  $$
    update public.usage_counters
    set count = 99
    where user_id = 'a1000000-0000-0000-0000-000000000021'
  $$,
  '42501',
  null,
  'anon cannot update usage_counters'
);

select throws_ok(
  $$
    delete from public.usage_counters
    where user_id = 'a1000000-0000-0000-0000-000000000021'
  $$,
  '42501',
  null,
  'anon cannot delete usage_counters'
);

select * from finish();

rollback;
