-- local development seed data
-- runs automatically after migrations via `supabase db reset`
-- password for both users: devpassword123 (local-only; never reuse elsewhere)

create extension if not exists pgcrypto;

-- dev users
-- user 1: dev1@example.com (free tier)
-- user 2: dev2@example.com (pro tier)

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
    '00000000-0000-0000-0000-000000000001',
    'authenticated',
    'authenticated',
    'dev1@example.com',
    crypt('devpassword123', gen_salt('bf')),
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
    '00000000-0000-0000-0000-000000000002',
    'authenticated',
    'authenticated',
    'dev2@example.com',
    crypt('devpassword123', gen_salt('bf')),
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

insert into auth.identities (
  id,
  user_id,
  identity_data,
  provider,
  provider_id,
  last_sign_in_at,
  created_at,
  updated_at
)
values
  (
    '00000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001',
    '{"sub": "00000000-0000-0000-0000-000000000001", "email": "dev1@example.com"}'::jsonb,
    'email',
    '00000000-0000-0000-0000-000000000001',
    now(),
    now(),
    now()
  ),
  (
    '00000000-0000-0000-0000-000000000002',
    '00000000-0000-0000-0000-000000000002',
    '{"sub": "00000000-0000-0000-0000-000000000002", "email": "dev2@example.com"}'::jsonb,
    'email',
    '00000000-0000-0000-0000-000000000002',
    now(),
    now(),
    now()
  )
on conflict do nothing;

-- profiles are auto-created by on_auth_user_created; set one user to pro for tier testing
update public.profiles
set tier = 'pro'
where id = '00000000-0000-0000-0000-000000000002';

-- sample analyses (illustrative result shapes for local UI/dev work)
-- no on conflict: db reset truncates first; ids are gen_random_uuid() with no natural duplicate key
insert into public.analyses (
  user_id,
  type,
  result,
  summary_return,
  instrument_count,
  created_at
)
values
  (
    '00000000-0000-0000-0000-000000000001',
    'stock',
    '{
      "format": "detailed",
      "trades": [],
      "warnings": [],
      "notices": [],
      "pnl": {"total_pnl": 1250.50, "total_return_pct": 12.5},
      "commissions": {"total": 45.00},
      "significance": {"verdict": "insufficient_sample"}
    }'::jsonb,
    12.5,
    15,
    now() - interval '14 days'
  ),
  (
    '00000000-0000-0000-0000-000000000001',
    'options',
    '{
      "format": "detailed",
      "trades": [],
      "warnings": [],
      "notices": [],
      "pnl": {"total_pnl": -320.00, "total_return_pct": -8.2},
      "costs": {"total": 28.50},
      "significance": {"verdict": "insufficient_sample"}
    }'::jsonb,
    -8.2,
    8,
    now() - interval '7 days'
  ),
  (
    '00000000-0000-0000-0000-000000000002',
    'stock',
    '{
      "format": "detailed",
      "trades": [],
      "warnings": [],
      "notices": [],
      "pnl": {"total_pnl": 530.00, "total_return_pct": 5.3},
      "commissions": {"total": 62.00},
      "significance": {"verdict": "not_significant"}
    }'::jsonb,
    5.3,
    22,
    now() - interval '21 days'
  ),
  (
    '00000000-0000-0000-0000-000000000002',
    'options',
    '{
      "format": "detailed",
      "trades": [],
      "warnings": [],
      "notices": [],
      "pnl": {"total_pnl": 1870.00, "total_return_pct": 18.7},
      "costs": {"total": 41.25},
      "significance": {"verdict": "not_significant"}
    }'::jsonb,
    18.7,
    6,
    now() - interval '3 days'
  );

-- usage counters for the current month
insert into public.usage_counters (user_id, period, count)
values
  ('00000000-0000-0000-0000-000000000001', to_char(now(), 'YYYY-MM'), 2),
  ('00000000-0000-0000-0000-000000000002', to_char(now(), 'YYYY-MM'), 2)
on conflict (user_id, period) do nothing;
