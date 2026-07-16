begin;

select plan(8);

-- Fixture UUIDs distinct from seed.sql (00000000-...-0001/0002).
-- owner: a1000000-0000-0000-0000-000000000001
-- other: a1000000-0000-0000-0000-000000000002

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
    'a1000000-0000-0000-0000-000000000001',
    'authenticated',
    'authenticated',
    'rls-owner@example.com',
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
    'a1000000-0000-0000-0000-000000000002',
    'authenticated',
    'authenticated',
    'rls-other@example.com',
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

-- handle_new_user trigger creates profiles rows for both users.

-- owner
set local role authenticated;
set local request.jwt.claims = '{"sub": "a1000000-0000-0000-0000-000000000001"}';

select results_eq(
  $$
    select count(*)::int
    from public.profiles
    where id = 'a1000000-0000-0000-0000-000000000001'
  $$,
  ARRAY[1],
  'owner can select own profile'
);

select results_eq(
  $$
    with updated as (
      update public.profiles
      set updated_at = now()
      where id = 'a1000000-0000-0000-0000-000000000001'
      returning 1
    )
    select count(*)::int from updated
  $$,
  ARRAY[1],
  'owner can update own updated_at'
);

select throws_ok(
  $$
    update public.profiles
    set tier = 'pro'
    where id = 'a1000000-0000-0000-0000-000000000001'
  $$,
  '42501',
  null,
  'owner cannot update tier (column grant restriction)'
);

select throws_ok(
  $$
    insert into public.profiles (id, tier)
    values ('a1000000-0000-0000-0000-000000000001', 'free')
  $$,
  '42501',
  null,
  'authenticated cannot insert profiles'
);

-- other user
reset role;
set local role authenticated;
set local request.jwt.claims = '{"sub": "a1000000-0000-0000-0000-000000000002"}';

select results_eq(
  $$
    select count(*)::int
    from public.profiles
    where id = 'a1000000-0000-0000-0000-000000000001'
  $$,
  ARRAY[0],
  'other user cannot select owner profile'
);

select results_eq(
  $$
    with updated as (
      update public.profiles
      set updated_at = now()
      where id = 'a1000000-0000-0000-0000-000000000001'
      returning 1
    )
    select count(*)::int from updated
  $$,
  ARRAY[0],
  'other user cannot update owner profile'
);

-- anon
reset role;
set local request.jwt.claims = '{}';
set local role anon;

select throws_ok(
  'select * from public.profiles',
  '42501',
  null,
  'anon cannot select profiles'
);

select throws_ok(
  $$
    update public.profiles
    set updated_at = now()
    where id = 'a1000000-0000-0000-0000-000000000001'
  $$,
  '42501',
  null,
  'anon cannot update profiles'
);

select * from finish();

rollback;
