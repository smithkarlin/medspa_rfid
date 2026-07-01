import sqlite3

# 1. Connect to the database (creates 'medspa.db' file automatically)
conn = sqlite3.connect('medspa.db')
cursor = conn.cursor()

# 2. Create the Inventory Items Table
cursor.execute('''
CREATE TABLE IF NOT EXISTS inventory_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    sku TEXT UNIQUE NOT NULL
)
''')

# 3. Create the RFID Mappings Table
cursor.execute('''
CREATE TABLE IF NOT EXISTS rfid_mappings (
    epc_code TEXT PRIMARY KEY,
    inventory_item_id INTEGER,
    status TEXT DEFAULT 'In Stock',
    expiration_date TEXT,
    FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id)
)
''')
conn.commit()

print("Database and tables created successfully!")

# 4. Insert Some Test Data (Only runs if the database is empty)
try:
    cursor.execute("INSERT INTO inventory_items (product_name, sku) VALUES ('Botox 100 Units', 'BTX-100')")
    cursor.execute("INSERT INTO inventory_items (product_name, sku) VALUES ('Juvederm Ultra', 'JUV-ULT-01')")
    
    # Let's map 2 mock RFID tags to Botox (ID 1) and 1 tag to Juvederm (ID 2)
    cursor.execute("INSERT INTO rfid_mappings (epc_code, inventory_item_id, expiration_date) VALUES ('E28011302000A1', 1, '2027-06-30')")
    cursor.execute("INSERT INTO rfid_mappings (epc_code, inventory_item_id, expiration_date) VALUES ('E28011302000A2', 1, '2027-08-15')")
    cursor.execute("INSERT INTO rfid_mappings (epc_code, inventory_item_id, expiration_date) VALUES ('E28011302000B1', 2, '2028-01-01')")
    conn.commit()
    print("Sample items and RFID tags loaded!")
except sqlite3.IntegrityError:
    # This prevents errors if you run the script more than once
    print("Sample data already exists, skipping insertion.")

conn.close()
def scan_rfid_tag(mock_scanned_epc):
    """Simulates scanning an RFID tag and looks it up in the database."""
    conn = sqlite3.connect('medspa.db')
    cursor = conn.cursor()
    
    # Query to join the tables and find the item details
    query = '''
    SELECT inventory_items.product_name, rfid_mappings.status, rfid_mappings.expiration_date
    FROM rfid_mappings
    JOIN inventory_items ON rfid_mappings.inventory_item_id = inventory_items.id
    WHERE rfid_mappings.epc_code = ?
    '''
    
    cursor.execute(query, (mock_scanned_epc,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        product_name, status, exp_date = result
        print(f"\n📡 [SCANNER EVENT] Tag Detected: {mock_scanned_epc}")
        print(f"📦 Product: {product_name}")
        print(f"📊 Status: {status}")
        print(f"📅 Expires: {exp_date}\n")
    else:
        print(f"\n❌ Unknown Tag: {mock_scanned_epc} not found in database.")

# --- SIMULATE SCANS RIGHT HERE ---
# --- LIVE SCANNER EMULATOR ---
print("\n=== MED SPA RFID SYSTEM ACTIVE ===")
print("Type or paste an RFID Tag ID (EPC) and press Enter.")
print("Type 'exit' to turn off the system.\n")

while True:
    # This line stops the program and waits for you to input a tag ID
    user_input = input("📡 Awaiting RFID Scan: ").strip()
    
    if user_input.lower() == 'exit':
        print("Shutting down RFID System. Goodbye!")
        break
        
    if user_input == "":
        continue
        
    # Run our scanner function on whatever you typed
    scan_rfid_tag(user_input)