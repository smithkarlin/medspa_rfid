import sqlite3
from datetime import datetime, timedelta

# --- STEP 1: INITIALIZE ADVANCED SCHEMA ---
conn = sqlite3.connect('medspa.db')
cursor = conn.cursor()

# Update/Create Inventory master table with reorder thresholds
cursor.execute('''
CREATE TABLE IF NOT EXISTS inventory_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    sku TEXT UNIQUE NOT NULL,
    reorder_level INTEGER DEFAULT 3  -- Alert when stock drops to/below this
)
''')

# Update/Create RFID Mappings table with room locations
cursor.execute('''
CREATE TABLE IF NOT EXISTS rfid_mappings (
    epc_code TEXT PRIMARY KEY,
    inventory_item_id INTEGER,
    status TEXT DEFAULT 'In Stock',
    expiration_date TEXT,
    room_location TEXT DEFAULT 'Treatment Room 1',
    FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id)
)
''')
conn.commit()

# Clear old data to prevent conflicts with new columns
cursor.execute("DELETE FROM rfid_mappings")
cursor.execute("DELETE FROM inventory_items")
conn.commit()

# Load specific High-Value Doctor Inventory
cursor.execute("INSERT INTO inventory_items (product_name, sku, reorder_level) VALUES ('Premium Aesthetic Needle Pack (36-Pin)', 'NDL-36P', 5)")
cursor.execute("INSERT INTO inventory_items (product_name, sku, reorder_level) VALUES ('Luxury Vitamin C Facial Serum', 'SERUM-VC', 3)")
cursor.execute("INSERT INTO inventory_items (product_name, sku, reorder_level) VALUES ('Botox 100 Units (Vial)', 'BTX-100', 4)")
conn.commit()

# Simulate Room 1 Inventory Stock (Some expiring soon, some low stock)
today = datetime.now()
expiring_soon = (today + timedelta(days=45)).strftime('%Y-%m-%d')  # Expires in 45 days
healthy_date = (today + timedelta(days=365)).strftime('%Y-%m-%d') # Expires in a year

cursor.executemany('''
INSERT INTO rfid_mappings (epc_code, inventory_item_id, status, expiration_date, room_location)
VALUES (?, ?, ?, ?, ?)
''', [
    # 2 Serums expiring soon -> Good candidates for a flash sale!
    ('SERUM_TAG_01', 2, 'In Stock', expiring_soon, 'Treatment Room 1'),
    ('SERUM_TAG_02', 2, 'In Stock', expiring_soon, 'Treatment Room 1'),
    ('SERUM_TAG_03', 2, 'In Stock', healthy_date, 'Treatment Room 1'),
    
    # Only 2 Needle Packs left in stock -> Low stock alert (threshold is 5)
    ('NEEDLE_TAG_01', 1, 'In Stock', healthy_date, 'Treatment Room 1'),
    ('NEEDLE_TAG_02', 1, 'In Stock', healthy_date, 'Treatment Room 1'),
    
    # Plenty of Botox vials
    ('BOTOX_TAG_01', 3, 'In Stock', healthy_date, 'Treatment Room 1'),
    ('BOTOX_TAG_02', 3, 'In Stock', healthy_date, 'Treatment Room 1'),
    ('BOTOX_TAG_03', 3, 'In Stock', healthy_date, 'Treatment Room 1'),
    ('BOTOX_TAG_04', 3, 'In Stock', healthy_date, 'Treatment Room 1'),
    ('BOTOX_TAG_05', 3, 'In Stock', healthy_date, 'Treatment Room 1')
])
conn.commit()
conn.close()


# --- STEP 2: THE BUSINESS SMART ENGINE ---

def run_room_audit_report(room_name):
    """Analyzes scanned data for a room, finding low stock and expiring items."""
    conn = sqlite3.connect('medspa.db')
    cursor = conn.cursor()
    
    print(f"\n==============================================")
    print(f"📊 AUTOMATED AUDIT REPORT FOR: {room_name.upper()}")
    print(f"==============================================")
    
    # --- Part A: Find Facial Products to Put on Sale (Expiring in the next 60 days)
    two_months_from_now = (datetime.now() + timedelta(days=60)).strftime('%Y-%m-%d')
    
    cursor.execute('''
    SELECT inventory_items.product_name, rfid_mappings.epc_code, rfid_mappings.expiration_date
    FROM rfid_mappings
    JOIN inventory_items ON rfid_mappings.inventory_item_id = inventory_items.id
    WHERE rfid_mappings.room_location = ? 
      AND rfid_mappings.status = 'In Stock'
      AND rfid_mappings.expiration_date <= ?
    ''', (room_name, two_months_from_now))
    
    expiring_items = cursor.fetchall()
    
    print("\n🏷️  [PROMOTION FINDER] ITEMS TO PUT ON SALE (EXPIRING SOON):")
    if expiring_items:
        for item in expiring_items:
            print(f"   ⚠️  {item[0]} (Tag: {item[1]}) - Expires on {item[2]}! Run promo code.")
    else:
        print("   ✅ No items expiring soon.")

    # --- Part B: Find Low Stock Items to Reorder (Compare Count vs Reorder Level)
    cursor.execute('''
    SELECT inventory_items.product_name, inventory_items.reorder_level, COUNT(rfid_mappings.epc_code) as current_stock
    FROM inventory_items
    LEFT JOIN rfid_mappings ON inventory_items.id = rfid_mappings.inventory_item_id 
      AND rfid_mappings.status = 'In Stock' 
      AND rfid_mappings.room_location = ?
    GROUP BY inventory_items.id
    ''', (room_name,))
    
    stock_levels = cursor.fetchall()
    
    print("\n📦 [REORDER ENGINE] HIGH-VALUE STOCK LEVELS:")
    for product_name, threshold, current_stock in stock_levels:
        status_icon = "✅"
        alert_msg = ""
        if current_stock <= threshold:
            status_icon = "🚨"
            alert_msg = f" -> ORDER NOW! (Min threshold is {threshold})"
            
        print(f"   {status_icon} {product_name}: {current_stock} units on shelf{alert_msg}")
        
    print("==============================================\n")
    conn.close()

# Run the smart doctor report!
run_room_audit_report('Treatment Room 1')