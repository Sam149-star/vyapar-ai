from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
import time

def generate_invoice_pdf(data):
    """
    Generates a simple PDF invoice from data.
    data format: {"customer_name": "...", "items": [{"name": "...", "quantity": ..., "price": ...}]}
    Returns: Path to the generated PDF.
    """
    customer = data.get("customer_name", "Cash Customer")
    items = data.get("items", [])
    
    filename = f"invoice_{int(time.time())}.pdf"
    output_dir = "data/invoices"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    filepath = os.path.join(output_dir, filename)
    
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter
    
    # Header
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, height - 50, "VYAPAR AI INVOICE")
    
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 80, f"Customer: {customer}")
    c.drawString(400, height - 80, f"Date: {time.strftime('%Y-%m-%d')}")
    
    # Table Header
    y = height - 120
    c.line(50, y+5, 550, y+5)
    c.drawString(50, y, "Item")
    c.drawString(300, y, "Qty")
    c.drawString(400, y, "Price")
    c.drawString(500, y, "Total")
    c.line(50, y-5, 550, y-5)
    
    y -= 25
    total_amount = 0
    
    for item in items:
        name = item.get("name", "Unknown")
        qty = item.get("quantity") or 0
        price = item.get("price") or 0
        line_total = qty * price
        total_amount += line_total
        
        c.drawString(50, y, str(name))
        c.drawString(300, y, str(qty))
        c.drawString(400, y, f"{price:.2f}")
        c.drawString(500, y, f"{line_total:.2f}")
        y -= 20
        
    # Grand Total
    y -= 10
    c.line(50, y+15, 550, y+15)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(400, y, "Grand Total:")
    c.drawString(500, y, f"Rs. {total_amount:.2f}")
    
    c.save()
    print(f"Invoice generated: {filepath}")
    return filepath
