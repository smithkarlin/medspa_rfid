"""Seeds a small amount of demo data into Supabase so you can see the
Analytics dashboard populated. Run with: python3 "Make Meta Data.py"
"""
from datetime import datetime, timedelta

import db

today = datetime.now()

# 1. Seed some 'Used' RFID items for the line chart
test_rfid_data = [
    {"epc": "EPC001", "sku": "BTX-100U", "product_name": "Botox 100U",
     "commissioned_at": (today - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S'),
     "status": "Used", "location": "Treatment Room 1"},
    {"epc": "EPC002", "sku": "BTX-100U", "product_name": "Botox 100U",
     "commissioned_at": (today - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'),
     "status": "Used", "location": "Treatment Room 1"},
    {"epc": "EPC003", "sku": "JUV-ULTRA", "product_name": "Juvederm Ultra",
     "commissioned_at": (today - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S'),
     "status": "Used", "location": "Treatment Room 2"},
    {"epc": "EPC004", "sku": "JUV-ULTRA", "product_name": "Juvederm Ultra",
     "commissioned_at": (today - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'),
     "status": "Used", "location": "Treatment Room 2"},
    {"epc": "EPC005", "sku": "BTX-100U", "product_name": "Botox 100U",
     "commissioned_at": today.strftime('%Y-%m-%d %H:%M:%S'),
     "status": "In Stock", "location": "Main Vault / Refrigerator"},
]

# Make sure the referenced catalog SKUs exist first (tagged_inventory.sku is
# a foreign key into product_catalog).
catalog_rows = [
    {"sku": "BTX-100U", "barcode": "00300234567890", "product_name": "Botox 100U", "unit_cost": 625.00, "reorder_level": 10},
    {"sku": "JUV-ULTRA", "barcode": "00300987654321", "product_name": "Juvederm Ultra", "unit_cost": 275.00, "reorder_level": 5},
]
db.get_client().table("product_catalog").upsert(catalog_rows, on_conflict="sku").execute()
db.get_client().table("tagged_inventory").upsert(test_rfid_data, on_conflict="epc").execute()

# 2. Seed some Barcode items expiring soon for the donut chart & table
test_barcode_data = [
    {"barcode": "BC1001", "product_name": "Juvederm Voluma", "sku": "SKU-VOL-01",
     "expiration_date": (today + timedelta(days=15)).strftime('%Y-%m-%d'), "unit_cost": 450.00, "status": "In Stock"},
    {"barcode": "BC1002", "product_name": "Dysport 300U", "sku": "SKU-DYS-300",
     "expiration_date": (today + timedelta(days=45)).strftime('%Y-%m-%d'), "unit_cost": 280.00, "status": "In Stock"},
    {"barcode": "BC1003", "product_name": "Restylane Kysse", "sku": "SKU-RES-01",
     "expiration_date": (today - timedelta(days=5)).strftime('%Y-%m-%d'), "unit_cost": 320.00, "status": "In Stock"},
]
db.get_client().table("barcode_inventory").insert(test_barcode_data).execute()

print("✅ Test data seeded to Supabase! Refresh your Streamlit app to see the graphs.")
