from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/vyapar.db")

# Fix for Render/Postgres URL if it starts with postgres://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Ensure directory exists for sqlite fallback
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)

# Connect args (only for SQLite)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class InventoryItem(Base):
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    price = Column(Float)
    quantity = Column(Float, default=0.0)

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String)
    items_json = Column(String) # Storing list of items as JSON string for simplicity
    total_amount = Column(Float)
    date = Column(DateTime, default=datetime.utcnow)
    pdf_path = Column(String, nullable=True)

def init_db():
    Base.metadata.create_all(bind=engine)

# --- Helper Functions ---

def add_inventory(name: str, qty: float, price: float = 0):
    db = SessionLocal()
    try:
        item = db.query(InventoryItem).filter(InventoryItem.name == name).first()
        if item:
            item.quantity += qty
            if price > 0: item.price = price # Update price if provided
        else:
            item = InventoryItem(name=name, quantity=qty, price=price)
            db.add(item)
        db.commit()
        return f"Updated {name}: Qty {item.quantity}, Price {item.price}"
    finally:
        db.close()

def create_transaction(customer_name: str, items: list, total: float, pdf_path: str):
    import json
    db = SessionLocal()
    try:
        # Deduct inventory
        for i in items:
            db_item = db.query(InventoryItem).filter(InventoryItem.name == i['name']).first()
            if db_item:
                db_item.quantity -= i.get('quantity', 0)
        
        # Record Transaction
        txn = Transaction(
            customer_name=customer_name,
            items_json=json.dumps(items),
            total_amount=total,
            pdf_path=pdf_path
        )
        db.add(txn)
        db.commit()
        return f"Transaction recorded. Invoice generated."
    finally:
        db.close()

def get_ledger_summary(period="today"):
    db = SessionLocal()
    try:
        txns = db.query(Transaction).all()
        total_sales = sum([t.total_amount for t in txns])
        
        inventory = db.query(InventoryItem).all()
        stock_summary = "\nStock Levels:\n" + "\n".join([f"- {i.name}: {i.quantity}" for i in inventory]) if inventory else "\nNo inventory recorded."
        
        return f"Total Sales: Rs. {total_sales} ({len(txns)} txns).{stock_summary}"
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    print("Database Initialized.")
