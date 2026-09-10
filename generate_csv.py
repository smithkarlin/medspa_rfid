import csv

# Typical MDware export structure matching your Streamlit parser columns
mdware_headers = [
    "SKU / Item Code",
    "Barcode / UPC / GTIN",
    "Product Name / Description",
    "Category",
    "Unit Cost ($)",
    "Reorder Level",
    "Current Stock"
]

# Real-world medspa catalog data
sample_inventory_data = [
    [
        "BTX-100U",
        "00300234567890",
        "Botox Cosmetic 100 Units (OnabotulinumtoxinA)",
        "Neurotoxins",
        "625.00",
        "10",
        "42"
    ],
    [
        "DSP-300U",
        "00300456789012",
        "Dysport 300 Units (AbobotulinumtoxinA)",
        "Neurotoxins",
        "310.00",
        "8",
        "25"
    ],
    [
        "JUV-ULTRA",
        "00300987654321",
        "Juvederm Ultra XC 1.0ml",
        "Dermal Fillers",
        "275.00",
        "5",
        "18"
    ],
    [
        "JUV-VOLUMA",
        "00300987654322",
        "Juvederm Voluma XC 1.0ml",
        "Dermal Fillers",
        "320.00",
        "5",
        "14"
    ],
    [
        "RST-LYFT",
        "00732154987654",
        "Restylane Lyft 1.0ml with Lidocaine",
        "Dermal Fillers",
        "285.00",
        "6",
        "12"
    ],
    [
        "DP4-NEEDLES",
        "01234567890123",
        "Dermapen 4 Cartridges (Box of 33)",
        "Consumables",
        "150.00",
        "3",
        "9"
    ],
    [
        "LIDO-TX",
        "08899001122334",
        "Topical Numbing Cream 5% Lidocaine (450g)",
        "Topicals",
        "45.00",
        "4",
        "8"
    ]
]

def generate_mdware_csv(file_path="MDware_Inventory_Export.csv"):
    with open(file_path, mode="w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(mdware_headers)
        writer.writerows(sample_inventory_data)
    print(f"✅ Successfully created '{file_path}' with {len(sample_inventory_data)} product catalog items!")

if __name__ == "__main__":
    generate_mdware_csv()