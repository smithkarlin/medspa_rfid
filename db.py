"""
Supabase-backed data access layer for the tagmate RFID inventory app.

All Postgres access for interface.py and pages/2_Analytics.py goes through
this module instead of talking to sqlite3 directly. Connection details are
read from Streamlit secrets (.streamlit/secrets.toml) if present, otherwise
from environment variables loaded from a local .env file. See .env.example.
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


@st.cache_resource
def get_client() -> Client:
    url = _get_setting("SUPABASE_URL")
    key = _get_setting("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_KEY "
            "in a .env file or .streamlit/secrets.toml (see .env.example)."
        )
    return create_client(url, key)


def _is_unique_violation(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    return code == "23505" or "duplicate key value" in str(exc).lower()


# ---------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------
def get_locations_list() -> list:
    res = get_client().table("locations").select("location_name").order("location_name").execute()
    return [row["location_name"] for row in res.data]


def add_location(name: str) -> None:
    try:
        get_client().table("locations").insert({"location_name": name}).execute()
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


def sync_catalog(df_clean: pd.DataFrame) -> None:
    """Upsert catalog rows by SKU. Uses upsert (not replace) so it never
    breaks the tagged_inventory -> product_catalog foreign key."""
    df_clean = df_clean.copy()
    df_clean["unit_cost"] = df_clean["unit_cost"].astype(float)
    df_clean["reorder_level"] = df_clean["reorder_level"].astype(int)
    records = df_clean.to_dict("records")
    records = [{k: (v.item() if hasattr(v, "item") else v) for k, v in r.items()} for r in records]
    if records:
        get_client().table("product_catalog").upsert(records, on_conflict="sku").execute()


# ---------------------------------------------------------------------
# Tagged (RFID) inventory
# ---------------------------------------------------------------------
def insert_tagged_item(epc, sku, product_name, expiration_date, lot_number, location) -> None:
    try:
        get_client().table("tagged_inventory").insert({
            "epc": epc,
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
def insert_daily_audit(location, expected_count, scanned_count, discrepancy, audited_by) -> None:
    get_client().table("daily_audits").insert({
        "location": location,
        "expected_count": expected_count,
        "scanned_count": scanned_count,
        "discrepancy": discrepancy,
        "audited_by": audited_by,
    }).execute()


# ---------------------------------------------------------------------
# Generic fetch helper (used by the Analytics page)
# ---------------------------------------------------------------------
def fetch_df(table: str, columns=None) -> pd.DataFrame:
    """Fetch a whole table as a DataFrame. If `columns` is given, the result
    is reindexed to guarantee those columns exist even when the table is
    empty, so callers never hit a KeyError on a fresh, empty database."""
    res = get_client().table(table).select("*").execute()
    df = pd.DataFrame(res.data)
    if columns is not None:
        df = df.reindex(columns=columns)
    return df
