-- Additive migration: adds usage tracking so the app can compute a
-- historical consumption rate per product (used to power reorder
-- recommendations on the Vendors page). Does NOT drop or touch any
-- existing data.

alter table tagged_inventory add column if not exists used_at timestamptz;

-- No RLS changes needed: the existing "tagged_inventory: clinic isolation"
-- policy already covers reads/writes on this new column since Postgres
-- RLS policies apply per-row, not per-column.
