-- ============================================================
-- Migration 007: Stripe billing fields on clinics
--
-- Adds the columns needed to track each clinic's subscription: which
-- Stripe customer/subscription they're tied to, its current status, and
-- when a trial ends. No RLS changes needed for reading these -- the
-- existing "clinics: members can read their clinic" policy already
-- covers them.
--
-- Deliberately no UPDATE policy is added for clinics here. That's not an
-- oversight: an authenticated clinic admin must NOT be able to set their
-- own subscription_status to 'active' by calling the table directly --
-- only Stripe's own API response should ever be able to say a clinic is
-- paid. All billing writes go through db.get_service_client() (the
-- Supabase service-role key, which bypasses RLS) from server-side code
-- in billing.py, driven only by what Stripe actually reports.
--
-- Safe to run any number of times.
-- ============================================================

alter table clinics add column if not exists stripe_customer_id text;
alter table clinics add column if not exists stripe_subscription_id text;
alter table clinics add column if not exists subscription_status text;
alter table clinics add column if not exists subscription_plan text;
alter table clinics add column if not exists trial_ends_at timestamptz;
