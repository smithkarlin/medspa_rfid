-- ============================================================
-- Migration 005: fix infinite RLS recursion on profiles
--
-- migration_004_staff_invites.sql added a "profiles: admins read clinic
-- roster" policy that calls auth_clinic_id() and auth_is_admin() -- and
-- both of those functions query the profiles table themselves. Since
-- neither was marked security definer, that inner query got checked
-- against RLS too, which meant evaluating the policy required
-- re-evaluating the same policy, forever -- Postgres reports this as
-- "stack depth limit exceeded" (error 54001), and it broke login for
-- everyone, not just admins.
--
-- This just re-creates both functions as security definer so their
-- internal SELECT bypasses RLS instead of re-triggering it. Still
-- safe: both are hardcoded to auth.uid(), so they only ever reveal the
-- calling user's own clinic_id/role, never anyone else's -- same
-- reasoning already used for create_clinic_and_profile().
--
-- Safe to run any number of times.
-- ============================================================

create or replace function auth_clinic_id() returns uuid
language sql stable
security definer
set search_path = public
as $$
  select clinic_id from profiles where id = auth.uid()
$$;

create or replace function auth_is_admin() returns boolean
language sql stable
security definer
set search_path = public
as $$
  select coalesce((select role = 'admin' from profiles where id = auth.uid()), false)
$$;
