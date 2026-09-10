"""Seeds a small amount of demo data into YOUR clinic's Supabase tables so
you can see the Analytics dashboard populated.

Row Level Security means this can no longer write data anonymously -- it
signs in the same way the app does. Create an account and a clinic in the
app first (sign up, then "Create Clinic"), then run:
    python3 "Make Meta Data.py"
"""
import getpass
from datetime import datetime, timedelta

import db

email = input("tagmate account email: ").strip()
password = getpass.getpass("tagmate account password: ")

client = db.get_client()
result = client.auth.sign_in_with_password({"email": email, "password": password})
client.postgrest.auth(result.session.access_token)

profile_rows = client.table("profiles").select("*").eq("id", result.user.id).limit(1).execute().data
if not profile_rows:
    raise SystemExit(
        "No clinic set up yet for this account -- log into the app once and "
        "create your clinic first, then re-run this script."
    )
clinic_id = profile_rows[0]["clinic_id"]

today = datetime.now()

catalog_rows = [
    {"clinic_id": clinic_id, "sku": "BTX-100U", "barcode": "00300234567890",
     "product_name": "Botox 100U", "unit_cost": 625.00, "reorder_level": 10},
    {"clinic_id": clinic_id, "sku": "JUV-ULTRA", "barcode": "00300987654321",
     "product_name": "Juvederm Ultra", "unit_cost": 275.00, "reorder_level": 5},
]
client.table("product_catalog").upsert(catalog_rows, on_conflict="clinic_id,sku").execute()

# 1. Seed some 'Used' RFID items for the line chart
test_rfid_data = [
    {"epc": f"EPC00{i}-{clinic_id[:8]}", "clinic_id": clinic_id, "sku": sku, "product_name": name,
     "commissioned_at": ts.strftime('%Y-%m-%d %H:%M:%S'), "status": status, "location": location}
    for i, (sku, name, ts, status, location) in enumerate([
        ("BTX-100U", "Botox 100U", today - timedelta(days=2), "Used", "Treatment Room 1"),
        ("BTX-100U", "Botox 100U", today - timedelta(days=1), "Used", "Treatment Room 1"),
        ("JUV-ULTRA", "Juvederm Ultra", today - timedelta(days=3), "Used", "Treatment Room 2"),
        ("JUV-ULTRA", "Juvederm Ultra", today - timedelta(days=1), "Used", "Treatment Room 2"),
        ("BTX-100U", "Botox 100U", today, "In Stock", "Main Vault / Refrigerator"),
    ], start=1)
]
client.table("tagged_inventory").upsert(test_rfid_data, on_conflict="epc").execute()

# 2. Seed some Barcode items expiring soon for the donut chart & table
test_barcode_data = [
    {"clinic_id": clinic_id, "barcode": "BC1001", "product_name": "Juvederm Voluma", "sku": "SKU-VOL-01",
     "expiration_date": (today + timedelta(days=15)).strftime('%Y-%m-%d'), "unit_cost": 450.00, "status": "In Stock"},
    {"clinic_id": clinic_id, "barcode": "BC1002", "product_name": "Dysport 300U", "sku": "SKU-DYS-300",
     "expiration_date": (today + timedelta(days=45)).strftime('%Y-%m-%d'), "unit_cost": 280.00, "status": "In Stock"},
    {"clinic_id": clinic_id, "barcode": "BC1003", "product_name": "Restylane Kysse", "sku": "SKU-RES-01",
     "expiration_date": (today - timedelta(days=5)).strftime('%Y-%m-%d'), "unit_cost": 320.00, "status": "In Stock"},
]
client.table("barcode_inventory").insert(test_barcode_data).execute()

print("✅ Test data seeded to your clinic in Supabase! Refresh your Streamlit app to see the graphs.")
