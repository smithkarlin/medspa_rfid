import html

# Products matching your MDware setup
products = [
    {"sku": "BTX-100U", "name": "Botox 100U", "gtin": "00300234567890", "exp": "261231", "lot": "LOT998822"},
    {"sku": "DSP-300U", "name": "Dysport 300U", "gtin": "00300456789012", "exp": "270630", "lot": "AB7761"},
    {"sku": "JUV-ULTRA", "name": "Juvederm Ultra", "gtin": "00300987654321", "exp": "260815", "lot": "JUV1234"},
    {"sku": "JUV-VOLUMA", "name": "Juvederm Voluma", "gtin": "00300987654322", "exp": "261020", "lot": "VOL5544"},
    {"sku": "RST-LYFT", "name": "Restylane Lyft", "gtin": "00732154987654", "exp": "270115", "lot": "RST9021"}
]

html_content = """<!DOCTYPE html>
<html>
<head>
<style>
  body { font-family: Arial, sans-serif; margin: 20px; }
  .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }
  .label { border: 1px dashed #ccc; padding: 10px; border-radius: 4px; text-align: center; }
  .label img { width: 100px; height: 100px; }
  .info { font-size: 11px; margin-top: 5px; font-weight: bold; }
</style>
</head>
<body>
<h2>Printable Test Labels (Scan with 2D Reader)</h2>
<div class="grid">
"""

for p in products:
    gs1_str = f"01{p['gtin']}17{p['exp']}10{p['lot']}"
    # Uses TEC-IT web API to render real GS1 DataMatrix images dynamically
    img_url = f"https://barcode.tec-it.com/barcode.ashx?data={gs1_str}&code=GS1DataMatrix&translate-esc=true"
    
    html_content += f"""
  <div class="label">
    <img src="{img_url}" alt="Barcode">
    <div class="info">{html.escape(p['name'])}</div>
    <div style="font-size: 9px;">LOT: {html.escape(p['lot'])} | EXP: {html.escape(p['exp'])}</div>
  </div>
"""

html_content += """
</div>
</body>
</html>
"""

with open("print_labels.html", "w") as f:
    f.write(html_content)

print("Saved print_labels.html — open it in your browser and press Ctrl+P / Cmd+P to print!")