-- ============================================================
-- Migration 006: make RFID tags unique per-clinic, not globally
--
-- tagged_inventory.epc was the table's PRIMARY KEY, which means the
-- exact same physical RFID tag number could never be used by two
-- different clinics anywhere in the whole database -- even though each
-- clinic's data is otherwise fully isolated by Row Level Security.
--
-- That mismatch produced exactly the confusing symptom you saw: Checkout
-- (a SELECT) is filtered by RLS to your own clinic, so a tag belonging to
-- some other clinic correctly looks "not found" to you. But Express
-- Intake (an INSERT) hits the raw PRIMARY KEY constraint, which applies
-- across ALL clinics regardless of RLS -- so the very same tag comes back
-- "already assigned to another item," even though that other item isn't
-- yours and isn't visible to you. Two different clinics using identically
-- numbered generic RFID tags is common and should be completely fine.
--
-- This migration swaps the primary key for a surrogate id and replaces
-- it with a UNIQUE constraint scoped to (clinic_id, epc) -- so a tag only
-- has to be unique within its own clinic, never across clinics. Existing
-- data was already globally unique on epc, which is a strictly stronger
-- condition, so this is a safe, non-destructive change with nothing to
-- clean up first.
--
-- Safe to run once; re-running is harmless (each step is guarded).
-- ============================================================

alter table tagged_inventory add column if not exists id uuid default gen_random_uuid();
update tagged_inventory set id = gen_random_uuid() where id is null;
alter table tagged_inventory alter column id set not null;

alter table tagged_inventory drop constraint if exists tagged_inventory_pkey;
alter table tagged_inventory add primary key (id);

alter table tagged_inventory drop constraint if exists tagged_inventory_clinic_epc_unique;
alter table tagged_inventory add constraint tagged_inventory_clinic_epc_unique unique (clinic_id, epc);
