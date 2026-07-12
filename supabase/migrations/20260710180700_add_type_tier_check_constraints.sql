-- 20260710180700
-- add_type_tier_check_constraints.sql

alter table public.analyses
  add constraint analyses_type_check check (type in ('stock', 'options'));

-- 'pro' is the assumed tier value for paid users; confirm before EPIC 17 lands.
alter table public.profiles
  add constraint profiles_tier_check check (tier in ('free', 'pro'));
