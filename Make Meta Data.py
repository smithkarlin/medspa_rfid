import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect("medspa.db")
cursor = conn.cursor()

# 1. Seed some 'Used' RFID items for the line chart
today = datetime.now()
test_rfid_data = [
    ('EPC001', 'SKU-BOT-100', 'Botox 100U', (today - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S'), 'Used', 'Room 1'),
    ('EPC002', 'SKU-BOT-100', 'Botox 100U', (today - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'), 'Used', 'Room 1'),
    ('EPC003', 'SKU-JUV-001', 'Juvederm Ultra', (today - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S'), 'Used', 'Room 2'),
    ('EPC004', 'SKU-JUV-001', 'Juvederm Ultra', (today - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'), 'Used', 'Room 2'),
    ('EPC005', 'SKU-BOT-100', 'Botox 100U', today.strftime('%Y-%m-%d %H:%M:%S'), 'In Stock', 'Fridge 1'),
]

cursor.executemany("""
    INSERT OR REPLACE INTO tagged_inventory (epc, sku, product_name, commissioned_at, status, location)
    VALUES (?, ?, ?, ?, ?, ?)
""", test_rfid_data)

# 2. Seed some Barcode items expiring soon for the donut chart & table
test_barcode_data = [
    ('BC1001', 'Juvederm Voluma', 'SKU-VOL-01', (today + timedelta(days=15)).strftime('%Y-%m-%d'), 450.00, 'In Stock'),
    ('BC1002', 'Dysport 300U', 'SKU-DYS-300', (today + timedelta(days=45)).strftime('%Y-%m-%d'), 280.00, 'In Stock'),
    ('BC1003', 'Restylane Kysse', 'SKU-RES-01', (today - timedelta(days=5)).strftime('%Y-%m-%d'), 320.00, 'In Stock'),
]

cursor.executemany("""
    INSERT INTO barcode_inventory (barcode, product_name, sku, expiration_date, unit_cost, status)
    VALUES (?, ?, ?, ?, ?, ?)
""", test_barcode_data)

conn.commit()
conn.close()
print("✅ Test data seeded! Refresh your Streamlit app to see the graphs.")