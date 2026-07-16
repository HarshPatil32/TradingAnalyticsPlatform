begin;

select plan(12);

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
    'a1000000-0000-0000-0000-000000000011',
    'authenticated',
    'authenticated',
    'rls-analyses-owner@example.com',
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
    'a1000000-0000-0000-0000-000000000012',
    'authenticated',
    'authenticated',
    'rls-analyses-other@example.com',
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

insert into public.analyses (id, user_id, type, result)
values
  (
    'b1000000-0000-0000-0000-000000000011',
    'a1000000-0000-0000-0000-000000000011',
    'stock',
    '{"format": "detailed"}'::jsonb
  ),
  (
    'b1000000-0000-0000-0000-000000000012',
    'a1000000-0000-0000-0000-000000000012',
    'options',
    '{"format": "detailed"}'::jsonb
  );

-- owner
set local role authenticated;
set local request.jwt.claims = '{"sub": "a1000000-0000-0000-0000-000000000011"}';

select results_eq(
  $$
    select count(*)::int
    from public.analyses
    where user_id = 'a1000000-0000-0000-0000-000000000011'
  $$,
  ARRAY[1],
  'owner can select own analyses'
);

select lives_ok(
  $$
    insert into public.analyses (id, user_id, type, result)
    values (
      'b1000000-0000-0000-0000-000000000019',
      'a1000000-0000-0000-0000-000000000011',
      'stock',
      '{"format": "detailed"}'::jsonb
    )
  $$,
  'owner can insert own analysis'
);

select throws_ok(
  $$
    insert into public.analyses (id, user_id, type, result)
    values (
      'b1000000-0000-0000-0000-000000000020',
      'a1000000-0000-0000-0000-000000000012',
      'stock',
      '{"format": "detailed"}'::jsonb
    )
  $$,
  '42501',
  null,
  'owner cannot insert analysis for another user'
);

select results_eq(
  $$
    with updated as (
      update public.analyses
      set summary_return = 1.0
      where id = 'b1000000-0000-0000-0000-000000000011'
      returning 1
    )
    select count(*)::int from updated
  $$,
  ARRAY[1],
  'owner can update own analysis'
);

select results_eq(
  $$
    with deleted as (
      delete from public.analyses
      where id = 'b1000000-0000-0000-0000-000000000019'
      returning 1
    )
    select count(*)::int from deleted
  $$,
  ARRAY[1],
  'owner can delete own analysis'
);

-- other user
reset role;
set local role authenticated;
set local request.jwt.claims = '{"sub": "a1000000-0000-0000-0000-000000000012"}';

select results_eq(
  $$
    select count(*)::int
    from public.analyses
    where id = 'b1000000-0000-0000-0000-000000000011'
  $$,
  ARRAY[0],
  'other user cannot select owner analysis'
);

select results_eq(
  $$
    with updated as (
      update public.analyses
      set summary_return = 99.0
      where id = 'b1000000-0000-0000-0000-000000000011'
      returning 1
    )
    select count(*)::int from updated
  $$,
  ARRAY[0],
  'other user cannot update owner analysis'
);

select results_eq(
  $$
    with deleted as (
      delete from public.analyses
      where id = 'b1000000-0000-0000-0000-000000000011'
      returning 1
    )
    select count(*)::int from deleted
  $$,
  ARRAY[0],
  'other user cannot delete owner analysis'
);

-- anon
reset role;
set local request.jwt.claims = '{}';
set local role anon;

select throws_ok(
  'select * from public.analyses',
  '42501',
  null,
  'anon cannot select analyses'
);

select throws_ok(
  $$
    insert into public.analyses (user_id, type, result)
    values (
      'a1000000-0000-0000-0000-000000000011',
      'stock',
      '{"format": "detailed"}'::jsonb
    )
  $$,
  '42501',
  null,
  'anon cannot insert analyses'
);

select throws_ok(
  $$
    update public.analyses
    set summary_return = 1.0
    where id = 'b1000000-0000-0000-0000-000000000011'
  $$,
  '42501',
  null,
  'anon cannot update analyses'
);

select throws_ok(
  $$
    delete from public.analyses
    where id = 'b1000000-0000-0000-0000-000000000011'
  $$,
  '42501',
  null,
  'anon cannot delete analyses'
);

select * from finish();

rollback;
