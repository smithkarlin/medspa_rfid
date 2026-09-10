-- Migration 002: Vendor Management
-- Run this ONCE on your EXISTING Supabase project (the one you already
-- ran schema.sql v2 on) to add vendor tracking without losing your
-- existing clinic, login, or data. This does NOT drop anything.
--
-- Starting a brand-new project instead? Skip this file -- schema.sql
-- already includes vendors from the start.

create table if not exists vendors (
    id uuid primary key default gen_random_uuid(),
    clinic_id uuid not null references clinics(id) on delete cascade,
    vendor_name text not null,
    contact_name text,
    contact_email text,
    contact_phone text,
    lead_time_days integer,
    notes text,
    created_at timestamptz default now(),
    unique (clinic_id, vendor_name)
);

alter table product_catalog add column if not exists vendor_id uuid references vendors(id) on delete set null;

alter table vendors enable row level security;

create policy "vendors: clinic isolation" on vendors
    for all using (clinic_id = auth_clinic_id()) with check (clinic_id = auth_clinic_id());
