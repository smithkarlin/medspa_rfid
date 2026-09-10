-- ============================================================
-- tagmate multi-tenant schema (v2)
-- Run this in the Supabase SQL Editor.
--
-- This REPLACES the single-tenant schema from the first migration. If
-- you already ran the earlier schema.sql, this drops those tables
-- (and any test data in them) and rebuilds them with a clinic_id on
-- every row, plus Row Level Security so one clinic's login can never
-- see another clinic's data.
-- ============================================================

create extension if not exists pgcrypto;

-- ---- Tenancy ----

create table if not exists clinics (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    created_at timestamptz default now()
);

-- One row per Supabase Auth user, linking their login to a clinic.
create table if not exists profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    clinic_id uuid not null references clinics(id) on delete cascade,
    full_name text,
    role text not null default 'admin' check (role in ('admin', 'staff')),
    created_at timestamptz default now()
);

-- Drop old single-tenant tables from the first migration, if present.
-- CASCADE also removes anything built on top of them (e.g. an "inventory"
-- table or "expiration_risk" view some earlier exploration left behind).
drop table if exists daily_audits cascade;
drop table if exists tagged_inventory cascade;
drop table if exists barcode_inventory cascade;
drop table if exists locations cascade;
drop table if exists product_catalog cascade;
drop table if exists inventory cascade;
drop view if exists expiration_risk cascade;

-- ---- Per-clinic data ----

create table product_catalog (
    id uuid primary key default gen_random_uuid(),
    clinic_id uuid not null references clinics(id) on delete cascade,
    sku text not null,
    barcode text,
    product_name text not null,
    unit_cost numeric default 0.0,
    reorder_level integer default 5,
    unique (clinic_id, sku)
);

create table locations (
    id uuid primary key default gen_random_uuid(),
    clinic_id uuid not null references clinics(id) on delete cascade,
    location_name text not null,
    unique (clinic_id, location_name)
);

create table tagged_inventory (
    epc text primary key,
    clinic_id uuid not null references clinics(id) on delete cascade,
    sku text not null,
    product_name text not null,
    expiration_date date,
    lot_number text,
    location text not null,
    status text default 'In Stock',
    commissioned_at timestamptz default now(),
    last_scanned_at timestamptz,
    foreign key (clinic_id, sku) references product_catalog (clinic_id, sku)
);

create table daily_audits (
    audit_id uuid primary key default gen_random_uuid(),
    clinic_id uuid not null references clinics(id) on delete cascade,
    audit_date timestamptz default now(),
    location text not null,
    expected_count integer,
    scanned_count integer,
    discrepancy integer,
    audited_by text
);

create table barcode_inventory (
    id uuid primary key default gen_random_uuid(),
    clinic_id uuid not null references clinics(id) on delete cascade,
    barcode text,
    product_name text,
    sku text,
    expiration_date date,
    received_date timestamptz default now(),
    unit_cost numeric default 0.0,
    status text default 'In Stock',
    location text default 'Main Facility'
);

-- ---- Row Level Security: the actual wall between clinics ----
-- This is enforced by Postgres itself, not by the app -- even if someone
-- inspected the app's network traffic and replayed a request, the
-- database itself refuses to return or accept rows for a clinic that
-- isn't theirs.

alter table clinics enable row level security;
alter table profiles enable row level security;
alter table product_catalog enable row level security;
alter table locations enable row level security;
alter table tagged_inventory enable row level security;
alter table daily_audits enable row level security;
alter table barcode_inventory enable row level security;

-- Looks up the calling user's clinic_id from their profile row.
create or replace function auth_clinic_id() returns uuid
language sql stable
as $$
  select clinic_id from profiles where id = auth.uid()
$$;

create policy "profiles: read own row" on profiles
    for select using (id = auth.uid());
create policy "profiles: insert own row" on profiles
    for insert with check (id = auth.uid());
create policy "profiles: update own row" on profiles
    for update using (id = auth.uid());

create policy "clinics: members can read their clinic" on clinics
    for select using (id = auth_clinic_id());

-- Deliberately no direct INSERT policy on clinics: a brand-new user has no
-- profile row yet, so the SELECT policy above can't see a clinic they just
-- inserted themselves (INSERT ... RETURNING is itself subject to the
-- SELECT policy in Postgres RLS). Instead, clinic creation goes through
-- this SECURITY DEFINER function, which runs as the table owner and so
-- isn't subject to RLS for its own inserts -- it still sees the calling
-- user correctly via auth.uid(), it just isn't blocked by the chicken-
-- and-egg SELECT policy while doing the initial setup.
create or replace function create_clinic_and_profile(clinic_name text, full_name text)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  new_clinic_id uuid;
begin
  if auth.uid() is null then
    raise exception 'Not authenticated';
  end if;

  insert into clinics (name) values (clinic_name) returning id into new_clinic_id;

  insert into profiles (id, clinic_id, full_name, role)
  values (auth.uid(), new_clinic_id, full_name, 'admin');

  return new_clinic_id;
end;
$$;

grant execute on function create_clinic_and_profile(text, text) to authenticated;

create policy "product_catalog: clinic isolation" on product_catalog
    for all using (clinic_id = auth_clinic_id()) with check (clinic_id = auth_clinic_id());

create policy "locations: clinic isolation" on locations
    for all using (clinic_id = auth_clinic_id()) with check (clinic_id = auth_clinic_id());

create policy "tagged_inventory: clinic isolation" on tagged_inventory
    for all using (clinic_id = auth_clinic_id()) with check (clinic_id = auth_clinic_id());

create policy "daily_audits: clinic isolation" on daily_audits
    for all using (clinic_id = auth_clinic_id()) with check (clinic_id = auth_clinic_id());

create policy "barcode_inventory: clinic isolation" on barcode_inventory
    for all using (clinic_id = auth_clinic_id()) with check (clinic_id = auth_clinic_id());
