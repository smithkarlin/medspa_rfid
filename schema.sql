-- tagmate RFID inventory: Supabase (Postgres) schema
-- Run this once in the Supabase SQL Editor (Project -> SQL Editor -> New query).

create table if not exists product_catalog (
    sku text primary key,
    barcode text,
    product_name text not null,
    unit_cost numeric default 0.0,
    reorder_level integer default 5
);

create table if not exists locations (
    id bigint generated always as identity primary key,
    location_name text unique not null
);

create table if not exists tagged_inventory (
    epc text primary key,
    sku text not null references product_catalog(sku),
    product_name text not null,
    expiration_date date,
    lot_number text,
    location text not null,
    status text default 'In Stock',
    commissioned_at timestamptz default now(),
    last_scanned_at timestamptz
);

create table if not exists daily_audits (
    audit_id bigint generated always as identity primary key,
    audit_date timestamptz default now(),
    location text not null,
    expected_count integer,
    scanned_count integer,
    discrepancy integer,
    audited_by text
);

create table if not exists barcode_inventory (
    id bigint generated always as identity primary key,
    barcode text,
    product_name text,
    sku text,
    expiration_date date,
    received_date timestamptz default now(),
    unit_cost numeric default 0.0,
    status text default 'In Stock',
    location text default 'Main Facility'
);

insert into locations (location_name) values
    ('Treatment Room 1'),
    ('Treatment Room 2'),
    ('Main Vault / Refrigerator'),
    ('Back Office Storage')
on conflict (location_name) do nothing;

-- Note: Row Level Security is left off these tables (Supabase's default for
-- tables created via SQL). This app has no per-user login of its own -- it's
-- an internal clinic tool -- so access is controlled by keeping your API
-- keys private, the same trust model the old local SQLite file had. If you
-- later add staff logins, enable RLS and add policies before that point.
