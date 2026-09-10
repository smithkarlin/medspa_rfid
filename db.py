"""
Supabase-backed data access layer for the Tagmate RFID inventory app.

All Postgres access for interface.py and pages/2_Analytics.py goes through
this module instead of talking to sqlite3 directly. Connection details are
read from Streamlit secrets (.streamlit/secrets.toml) if present, otherwise
from environment variables loaded from a local .env file. See .env.example.

get_client() returns ONE Supabase client per browser session (stored in
st.session_state), not a single shared/cached client for the whole server
process. That matters once a user logs in: the client then carries that
user's auth token, and a shared client would leak one visitor's session
into another visitor's browser tab. Row-level security on every table
means reads never need an explicit clinic_id filter here -- Postgres
already restricts a signed-in user to their own clinic's rows. Inserts
still take an explicit clinic_id because RLS validates it, it doesn't
invent it.
"""
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


class DuplicateError(Exception):
    """Raised when an insert violates a unique constraint (duplicate EPC or location name)."""


def _get_setting(key: str):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key)


def get_client() -> Client:
    if "_sb_client" not in st.session_state:
        url = _get_setting("SUPABASE_URL")
        key = _get_setting("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError(
                "Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_KEY "
                "in a .env file or .streamlit/secrets.toml (see .env.example)."
            )
        st.session_state["_sb_client"] = create_client(url, key)
    return st.session_state["_sb_client"]


def _is_unique_violation(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    return code == "23505" or "duplicate key value" in str(exc).lower()


# ---------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------
def get_locations_list() -> list:
    res = get_client().table("locations").select("location_name").order("location_name").execute()
    return [row["location_name"] for row in res.data]


def add_location(name: str, clinic_id: str) -> None:
    try:
        get_client().table("locations").insert({"location_name": name, "clinic_id": clinic_id}).execute()
    except Exception as exc:
        if _is_unique_violation(exc):
            raise DuplicateError(f"Location '{name}' already exists.") from exc
        raise


def delete_location(name: str) -> None:
    get_client().table("locations").delete().eq("location_name", name).execute()


# ---------------------------------------------------------------------
# Product catalog
# ---------------------------------------------------------------------
def get_catalog_options() -> dict:
    res = get_client().table("product_catalog").select("sku, product_name").execute()
    return {row["sku"]: row["product_name"] for row in res.data}


def lookup_barcode_in_catalog(barcode_or_gtin: str):
    value = barcode_or_gtin.strip()
    res = (
        get_client()
        .table("product_catalog")
        .select("sku, product_name")
        .or_(f"barcode.eq.{value},sku.eq.{value}")
        .limit(1)
        .execute()
    )
    if res.data:
        row = res.data[0]
        return row["sku"], row["product_name"]
    return None


def sync_catalog(df_clean: pd.DataFrame, clinic_id: str) -> None:
    """Upsert catalog rows by (clinic_id, sku). Uses upsert (not replace) so
    it never breaks the tagged_inventory -> product_catalog foreign key."""
    df_clean = df_clean.copy()
    df_clean["unit_cost"] = df_clean["unit_cost"].astype(float)
    df_clean["reorder_level"] = df_clean["reorder_level"].astype(int)
    df_clean["clinic_id"] = clinic_id
    records = df_clean.to_dict("records")
    records = [{k: (v.item() if hasattr(v, "item") else v) for k, v in r.items()} for r in records]
    if records:
        get_client().table("product_catalog").upsert(records, on_conflict="clinic_id,sku").execute()


# ---------------------------------------------------------------------
# Tagged (RFID) inventory
# ---------------------------------------------------------------------
def insert_tagged_item(epc, sku, product_name, expiration_date, lot_number, location, clinic_id) -> None:
    try:
        get_client().table("tagged_inventory").insert({
            "epc": epc,
            "clinic_id": clinic_id,
            "sku": sku,
            "product_name": product_name,
            "expiration_date": str(expiration_date),
            "lot_number": lot_number,
            "location": location,
        }).execute()
    except Exception as exc:
        if _is_unique_violation(exc):
            raise DuplicateError(f"RFID tag '{epc}' is already assigned to another item.") from exc
        raise


def get_expected_count(location: str) -> int:
    res = (
        get_client()
        .table("tagged_inventory")
        .select("epc", count="exact")
        .eq("location", location)
        .eq("status", "In Stock")
        .execute()
    )
    return res.count or 0


def get_tagged_item(epc: str):
    res = (
        get_client()
        .table("tagged_inventory")
        .select("product_name, location, status, lot_number")
        .eq("epc", epc)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def update_tagged_location(epc: str, new_location: str, scanned_at: str) -> None:
    get_client().table("tagged_inventory").update({
        "location": new_location,
        "last_scanned_at": scanned_at,
        "status": "In Stock",
    }).eq("epc", epc).execute()


def get_all_tagged_inventory_df() -> pd.DataFrame:
    res = (
        get_client()
        .table("tagged_inventory")
        .select("*")
        .order("commissioned_at", desc=True)
        .execute()
    )
    df = pd.DataFrame(res.data)
    if df.empty:
        return df
    return df.rename(columns={
        "epc": "RFID Tag (EPC)",
        "product_name": "Product Name",
        "location": "Storage Location",
        "expiration_date": "Expiration Date",
        "lot_number": "Lot Number",
        "status": "Status",
        "commissioned_at": "Commissioned At",
        "last_scanned_at": "Last Scanned At",
    })[["RFID Tag (EPC)", "Product Name", "Storage Location", "Expiration Date",
        "Lot Number", "Status", "Commissioned At", "Last Scanned At"]]


# ---------------------------------------------------------------------
# Daily audits
# ---------------------------------------------------------------------
def insert_daily_audit(location, expected_count, scanned_count, discrepancy, audited_by, clinic_id) -> None:
    get_client().table("daily_audits").insert({
        "clinic_id": clinic_id,
        "location": location,
        "expected_count": expected_count,
        "scanned_count": scanned_count,
        "discrepancy": discrepancy,
        "audited_by": audited_by,
    }).execute()


# ---------------------------------------------------------------------
# Vendors
# ---------------------------------------------------------------------
def get_vendors_df() -> pd.DataFrame:
    res = get_client().table("vendors").select("*").order("vendor_name").execute()
    return pd.DataFrame(res.data)


def add_vendor(vendor_name, clinic_id, contact_name="", contact_email="",
                contact_phone="", lead_time_days=None, notes="") -> None:
    try:
        get_client().table("vendors").insert({
            "clinic_id": clinic_id,
            "vendor_name": vendor_name,
            "contact_name": contact_name or None,
            "contact_email": contact_email or None,
            "contact_phone": contact_phone or None,
            "lead_time_days": lead_time_days,
            "notes": notes or None,
        }).execute()
    except Exception as exc:
        if _is_unique_violation(exc):
            raise DuplicateError(f"Vendor '{vendor_name}' already exists.") from exc
        raise


def delete_vendor(vendor_id: str) -> None:
    get_client().table("vendors").delete().eq("id", vendor_id).execute()


def assign_vendor_to_skus(vendor_id, skus: list) -> None:
    if skus:
        get_client().table("product_catalog").update({"vendor_id": vendor_id}).in_("sku", skus).execute()


def unassign_vendor_from_skus(skus: list) -> None:
    if skus:
        get_client().table("product_catalog").update({"vendor_id": None}).in_("sku", skus).execute()


# ---------------------------------------------------------------------
# Generic fetch helper (used by the Analytics and Vendors pages)
# ---------------------------------------------------------------------
def fetch_df(table: str, columns=None) -> pd.DataFrame:
    """Fetch a whole table as a DataFrame. Row Level Security means this
    only ever returns the signed-in user's own clinic's rows. If `columns`
    is given, the result is reindexed to guarantee those columns exist even
    when the table is empty, so callers never hit a KeyError on a fresh,
    empty clinic."""
    res = get_client().table(table).select("*").execute()
    df = pd.DataFrame(res.data)
    if columns is not None:
        df = df.reindex(columns=columns)
    return df


# ---------------------------------------------------------------------
# Barcode (non-RFID) inventory
# ---------------------------------------------------------------------
def insert_barcode_item(barcode, product_name, sku, expiration_date, unit_cost,
                          location, clinic_id, status="In Stock") -> None:
    get_client().table("barcode_inventory").insert({
        "clinic_id": clinic_id,
        "barcode": barcode,
        "product_name": product_name,
        "sku": sku,
        "expiration_date": str(expiration_date),
        "unit_cost": float(unit_cost),
        "status": status,
        "location": location,
    }).execute()


# ---------------------------------------------------------------------
# Demo / sample data (so a brand-new clinic can preview the dashboards
# without scanning real inventory first)
# ---------------------------------------------------------------------
def load_sample_data(clinic_id: str) -> None:
    """Seeds 3 sample products across locations, vendor, RFID inventory,
    and barcode inventory, with staggered expiration dates so the
    Analytics and Vendors pages have something meaningful to show."""
    from datetime import date, timedelta

    for loc in ["Treatment Room 1", "Main Vault / Refrigerator"]:
        if loc not in get_locations_list():
            try:
                add_location(loc, clinic_id)
            except DuplicateError:
                pass

    try:
        add_vendor(
            "Allergan Direct", clinic_id,
            contact_name="Sam Rivera",
            contact_email="orders@allergandirect-demo.com",
            lead_time_days=5,
            notes="Sample vendor added by Load Sample Data.",
        )
    except DuplicateError:
        pass
    vendors_df = get_vendors_df()
    vendor_matches = vendors_df.loc[vendors_df["vendor_name"] == "Allergan Direct", "id"]
    vendor_id = vendor_matches.iloc[0] if not vendor_matches.empty else None

    sample_products = pd.DataFrame([
        {"sku": "BTX-100", "barcode": "00300090856100", "product_name": "Botox 100U", "unit_cost": 395.00, "reorder_level": 5},
        {"sku": "JUV-UXC", "barcode": "00300090862200", "product_name": "Juvederm Ultra XC", "unit_cost": 275.00, "reorder_level": 10},
        {"sku": "SERUM-VC", "barcode": "00300090899900", "product_name": "Vitamin C Facial Serum", "unit_cost": 68.00, "reorder_level": 8},
    ])
    sync_catalog(sample_products, clinic_id)
    if vendor_id is not None:
        assign_vendor_to_skus(vendor_id, ["BTX-100", "JUV-UXC", "SERUM-VC"])

    today = date.today()
    demo_items = [
        # epc,               sku,          product name,               days_to_exp, lot,        location
        ("DEMO-TAG-001", "BTX-100", "Botox 100U", -5, "LOT-DEMO1", "Treatment Room 1"),
        ("DEMO-TAG-002", "JUV-UXC", "Juvederm Ultra XC", 25, "LOT-DEMO2", "Main Vault / Refrigerator"),
        ("DEMO-TAG-003", "SERUM-VC", "Vitamin C Facial Serum", 65, "LOT-DEMO3", "Treatment Room 1"),
    ]
    for epc, sku, name, days_out, lot, loc in demo_items:
        exp = today + timedelta(days=days_out)
        try:
            insert_tagged_item(epc, sku, name, exp, lot, loc, clinic_id)
        except DuplicateError:
            pass

    catalog_lookup = {r["sku"]: r for r in sample_products.to_dict("records")}
    for epc, sku, name, days_out, lot, loc in demo_items:
        exp = today + timedelta(days=days_out)
        row = catalog_lookup[sku]
        try:
            insert_barcode_item(row["barcode"], name, sku, exp, row["unit_cost"], loc, clinic_id)
        except Exception:
            pass
