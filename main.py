"""
Apple Tree Purchase Tracker - FastAPI Backend
"""

import os
import shutil
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, func, extract
from sqlalchemy.orm import sessionmaker, Session

from models import (
    Base, Category, Vendor, Invoice, InvoiceItem, 
    Product, DailySales, MonthlyBudget, PriceAlert
)
from ocr_processor import InvoiceOCRProcessor, ExtractedInvoice

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./purchase_tracker.db")
UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Database setup
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI
app = FastAPI(
    title="Apple Tree Purchase Tracker",
    description="Track vendor invoices, manage purchasing budgets, and analyze spending",
    version="1.0.0"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# Initialize OCR processor
ocr_processor = InvoiceOCRProcessor()


# Dependency for database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== PYDANTIC MODELS ====================

class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    target_budget_percent: Optional[float] = None

class CategoryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    target_budget_percent: Optional[float]

class VendorCreate(BaseModel):
    name: str
    category_id: Optional[int] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    contact_person: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None

class VendorResponse(BaseModel):
    id: int
    name: str
    category_id: Optional[int]
    category_name: Optional[str]
    address: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    is_active: bool

class InvoiceItemCreate(BaseModel):
    product_name: str
    quantity: float
    unit_price: float
    total_price: float
    unit: Optional[str] = None
    product_code: Optional[str] = None

class InvoiceCreate(BaseModel):
    vendor_id: int
    invoice_number: Optional[str] = None
    invoice_date: date
    received_date: Optional[date] = None
    total: float
    tax: Optional[float] = 0
    notes: Optional[str] = None
    items: List[InvoiceItemCreate] = []

class InvoiceResponse(BaseModel):
    id: int
    vendor_id: int
    vendor_name: str
    category_name: Optional[str]
    invoice_number: Optional[str]
    invoice_date: date
    total: float
    status: str
    item_count: int

class DailySalesCreate(BaseModel):
    sale_date: date
    gross_sales: float
    net_sales: Optional[float] = None
    transaction_count: Optional[int] = None
    notes: Optional[str] = None

class OCRResultResponse(BaseModel):
    vendor_name: Optional[str]
    vendor_address: Optional[str]
    vendor_phone: Optional[str]
    vendor_email: Optional[str]
    invoice_number: Optional[str]
    invoice_date: Optional[str]
    total: Optional[float]
    line_items: List[dict]
    confidence_score: float
    suggested_vendor_id: Optional[int] = None


# ==================== CATEGORY ENDPOINTS ====================

@app.get("/api/categories", response_model=List[CategoryResponse])
def list_categories(db: Session = Depends(get_db)):
    """List all categories"""
    return db.query(Category).all()

@app.post("/api/categories", response_model=CategoryResponse)
def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    """Create a new category"""
    db_category = Category(**category.dict())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@app.get("/api/categories/{category_id}")
def get_category(category_id: int, db: Session = Depends(get_db)):
    """Get category details with spending summary"""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Get current month spending
    now = datetime.now()
    month_start = date(now.year, now.month, 1)
    
    monthly_total = db.query(func.sum(Invoice.total)).join(Vendor).filter(
        Vendor.category_id == category_id,
        Invoice.invoice_date >= month_start
    ).scalar() or 0
    
    return {
        "id": category.id,
        "name": category.name,
        "description": category.description,
        "target_budget_percent": float(category.target_budget_percent) if category.target_budget_percent else None,
        "current_month_spending": float(monthly_total)
    }


# ==================== VENDOR ENDPOINTS ====================

@app.get("/api/vendors")
def list_vendors(
    category_id: Optional[int] = None,
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """List vendors with optional filtering"""
    query = db.query(Vendor)
    
    if category_id:
        query = query.filter(Vendor.category_id == category_id)
    if active_only:
        query = query.filter(Vendor.is_active == True)
    
    vendors = query.all()
    return [v.to_dict() for v in vendors]

@app.post("/api/vendors")
def create_vendor(vendor: VendorCreate, db: Session = Depends(get_db)):
    """Create a new vendor"""
    db_vendor = Vendor(**vendor.dict())
    db.add(db_vendor)
    db.commit()
    db.refresh(db_vendor)
    return db_vendor.to_dict()

@app.get("/api/vendors/{vendor_id}")
def get_vendor(vendor_id: int, db: Session = Depends(get_db)):
    """Get vendor details with recent invoices"""
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    # Get recent invoices
    recent_invoices = db.query(Invoice).filter(
        Invoice.vendor_id == vendor_id
    ).order_by(Invoice.invoice_date.desc()).limit(10).all()
    
    # Get spending stats
    total_spent = db.query(func.sum(Invoice.total)).filter(
        Invoice.vendor_id == vendor_id
    ).scalar() or 0
    
    invoice_count = db.query(func.count(Invoice.id)).filter(
        Invoice.vendor_id == vendor_id
    ).scalar() or 0
    
    return {
        **vendor.to_dict(),
        "total_spent": float(total_spent),
        "invoice_count": invoice_count,
        "recent_invoices": [inv.to_dict() for inv in recent_invoices]
    }

@app.put("/api/vendors/{vendor_id}")
def update_vendor(vendor_id: int, vendor: VendorCreate, db: Session = Depends(get_db)):
    """Update a vendor"""
    db_vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not db_vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    for key, value in vendor.dict().items():
        setattr(db_vendor, key, value)
    
    db.commit()
    db.refresh(db_vendor)
    return db_vendor.to_dict()


# ==================== INVOICE ENDPOINTS ====================

@app.get("/api/invoices")
def list_invoices(
    vendor_id: Optional[int] = None,
    category_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List invoices with filtering"""
    query = db.query(Invoice).join(Vendor)
    
    if vendor_id:
        query = query.filter(Invoice.vendor_id == vendor_id)
    if category_id:
        query = query.filter(Vendor.category_id == category_id)
    if start_date:
        query = query.filter(Invoice.invoice_date >= start_date)
    if end_date:
        query = query.filter(Invoice.invoice_date <= end_date)
    if status:
        query = query.filter(Invoice.status == status)
    
    total = query.count()
    invoices = query.order_by(Invoice.invoice_date.desc()).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "invoices": [inv.to_dict() for inv in invoices]
    }

@app.post("/api/invoices")
def create_invoice(invoice: InvoiceCreate, db: Session = Depends(get_db)):
    """Create a new invoice with line items"""
    # Verify vendor exists
    vendor = db.query(Vendor).filter(Vendor.id == invoice.vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    # Create invoice
    db_invoice = Invoice(
        vendor_id=invoice.vendor_id,
        invoice_number=invoice.invoice_number,
        invoice_date=invoice.invoice_date,
        received_date=invoice.received_date,
        total=invoice.total,
        tax=invoice.tax,
        notes=invoice.notes
    )
    db.add(db_invoice)
    db.flush()  # Get the ID
    
    # Add line items
    for item in invoice.items:
        db_item = InvoiceItem(
            invoice_id=db_invoice.id,
            product_name=item.product_name,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=item.total_price,
            unit=item.unit,
            product_code=item.product_code
        )
        db.add(db_item)
        
        # Update product catalog
        _update_product_catalog(db, item, vendor.id, invoice.invoice_date)
    
    db.commit()
    db.refresh(db_invoice)
    
    return db_invoice.to_dict(include_items=True)

@app.get("/api/invoices/{invoice_id}")
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Get invoice with all details"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    return invoice.to_dict(include_items=True)

@app.put("/api/invoices/{invoice_id}/status")
def update_invoice_status(invoice_id: int, status: str, db: Session = Depends(get_db)):
    """Update invoice status"""
    valid_statuses = ['pending', 'verified', 'paid', 'disputed']
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice.status = status
    if status == 'paid':
        invoice.payment_date = date.today()
    
    db.commit()
    return invoice.to_dict()

@app.delete("/api/invoices/{invoice_id}")
def delete_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Delete an invoice"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    db.delete(invoice)
    db.commit()
    return {"message": "Invoice deleted"}


# ==================== OCR ENDPOINTS ====================

@app.post("/api/ocr/process", response_model=OCRResultResponse)
async def process_invoice_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload an invoice image and extract data using OCR.
    Returns structured data for review before saving.
    """
    # Validate file type
    allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'application/pdf']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"File type not allowed. Must be: {allowed_types}")
    
    # Save file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    file_path = UPLOAD_DIR / filename
    
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Process with OCR
    try:
        result = ocr_processor.process_image(str(file_path))
    except Exception as e:
        # Return partial result on error
        return OCRResultResponse(
            vendor_name=None,
            vendor_address=None,
            vendor_phone=None,
            vendor_email=None,
            invoice_number=None,
            invoice_date=None,
            total=None,
            line_items=[],
            confidence_score=0.0,
            suggested_vendor_id=None
        )
    
    # Try to match vendor
    suggested_vendor_id = None
    if result.vendor_name:
        vendor = db.query(Vendor).filter(
            Vendor.name.ilike(f"%{result.vendor_name}%")
        ).first()
        if vendor:
            suggested_vendor_id = vendor.id
    
    return OCRResultResponse(
        vendor_name=result.vendor_name,
        vendor_address=result.vendor_address,
        vendor_phone=result.vendor_phone,
        vendor_email=result.vendor_email,
        invoice_number=result.invoice_number,
        invoice_date=result.invoice_date,
        total=result.total,
        line_items=[{
            'product_name': item.product_name,
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'total_price': item.total_price
        } for item in result.line_items],
        confidence_score=result.confidence_score,
        suggested_vendor_id=suggested_vendor_id
    )


# ==================== DASHBOARD/ANALYTICS ENDPOINTS ====================

@app.get("/api/dashboard/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    """Get dashboard summary data"""
    now = datetime.now()
    today = date.today()
    month_start = date(now.year, now.month, 1)
    week_start = today - timedelta(days=today.weekday())
    
    # Today's purchases
    today_total = db.query(func.sum(Invoice.total)).filter(
        Invoice.invoice_date == today
    ).scalar() or 0
    
    # This week's purchases
    week_total = db.query(func.sum(Invoice.total)).filter(
        Invoice.invoice_date >= week_start
    ).scalar() or 0
    
    # This month's purchases
    month_total = db.query(func.sum(Invoice.total)).filter(
        Invoice.invoice_date >= month_start
    ).scalar() or 0
    
    # Pending invoices
    pending_count = db.query(func.count(Invoice.id)).filter(
        Invoice.status == 'pending'
    ).scalar() or 0
    
    # Recent invoices
    recent_invoices = db.query(Invoice).order_by(
        Invoice.created_at.desc()
    ).limit(5).all()
    
    # Spending by category this month
    category_spending = db.query(
        Category.name,
        func.sum(Invoice.total).label('total')
    ).join(Vendor, Vendor.category_id == Category.id
    ).join(Invoice, Invoice.vendor_id == Vendor.id
    ).filter(Invoice.invoice_date >= month_start
    ).group_by(Category.name).all()
    
    return {
        "today_purchases": float(today_total),
        "week_purchases": float(week_total),
        "month_purchases": float(month_total),
        "pending_invoices": pending_count,
        "recent_invoices": [inv.to_dict() for inv in recent_invoices],
        "category_spending": [
            {"category": name, "total": float(total)} 
            for name, total in category_spending
        ]
    }

@app.get("/api/dashboard/spending-trend")
def get_spending_trend(
    days: int = Query(default=30, le=365),
    db: Session = Depends(get_db)
):
    """Get daily spending trend"""
    start_date = date.today() - timedelta(days=days)
    
    daily_spending = db.query(
        Invoice.invoice_date,
        func.sum(Invoice.total).label('total')
    ).filter(
        Invoice.invoice_date >= start_date
    ).group_by(Invoice.invoice_date
    ).order_by(Invoice.invoice_date).all()
    
    return [
        {"date": d.isoformat(), "total": float(total)}
        for d, total in daily_spending
    ]

@app.get("/api/dashboard/category-breakdown")
def get_category_breakdown(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Get spending breakdown by category"""
    if not start_date:
        start_date = date.today().replace(day=1)
    if not end_date:
        end_date = date.today()
    
    breakdown = db.query(
        Category.id,
        Category.name,
        Category.target_budget_percent,
        func.sum(Invoice.total).label('total'),
        func.count(Invoice.id).label('invoice_count')
    ).join(Vendor, Vendor.category_id == Category.id
    ).join(Invoice, Invoice.vendor_id == Vendor.id
    ).filter(
        Invoice.invoice_date >= start_date,
        Invoice.invoice_date <= end_date
    ).group_by(Category.id).all()
    
    return [
        {
            "category_id": cat_id,
            "category_name": name,
            "target_percent": float(target) if target else None,
            "total_spent": float(total),
            "invoice_count": count
        }
        for cat_id, name, target, total, count in breakdown
    ]

@app.get("/api/dashboard/budget-status")
def get_budget_status(db: Session = Depends(get_db)):
    """Get current month budget status vs actuals"""
    now = datetime.now()
    month_start = date(now.year, now.month, 1)
    
    # Get monthly sales (for calculating target amounts)
    monthly_sales = db.query(func.sum(DailySales.gross_sales)).filter(
        DailySales.sale_date >= month_start
    ).scalar() or 0
    
    # Get spending by category
    category_spending = db.query(
        Category.id,
        Category.name,
        Category.target_budget_percent,
        func.coalesce(func.sum(Invoice.total), 0).label('actual')
    ).outerjoin(Vendor, Vendor.category_id == Category.id
    ).outerjoin(Invoice, (Invoice.vendor_id == Vendor.id) & (Invoice.invoice_date >= month_start)
    ).group_by(Category.id).all()
    
    result = []
    for cat_id, name, target_pct, actual in category_spending:
        target_amount = float(monthly_sales) * (float(target_pct) / 100) if target_pct and monthly_sales else 0
        actual_float = float(actual)
        variance = target_amount - actual_float if target_amount else 0
        
        result.append({
            "category_id": cat_id,
            "category_name": name,
            "target_percent": float(target_pct) if target_pct else None,
            "target_amount": target_amount,
            "actual_amount": actual_float,
            "variance": variance,
            "status": "over" if variance < 0 else "under" if variance > 0 else "on_target"
        })
    
    return {
        "month": month_start.isoformat(),
        "monthly_sales": float(monthly_sales),
        "categories": result
    }


# ==================== DAILY SALES ENDPOINTS ====================

@app.get("/api/sales")
def list_sales(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 30,
    db: Session = Depends(get_db)
):
    """List daily sales records"""
    query = db.query(DailySales)
    
    if start_date:
        query = query.filter(DailySales.sale_date >= start_date)
    if end_date:
        query = query.filter(DailySales.sale_date <= end_date)
    
    sales = query.order_by(DailySales.sale_date.desc()).limit(limit).all()
    return [s.to_dict() for s in sales]

@app.post("/api/sales")
def create_sales(sales: DailySalesCreate, db: Session = Depends(get_db)):
    """Record daily sales"""
    # Check if exists
    existing = db.query(DailySales).filter(DailySales.sale_date == sales.sale_date).first()
    if existing:
        # Update instead
        for key, value in sales.dict().items():
            setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return existing.to_dict()
    
    db_sales = DailySales(**sales.dict())
    db.add(db_sales)
    db.commit()
    db.refresh(db_sales)
    return db_sales.to_dict()


# ==================== PRICE ALERTS ENDPOINTS ====================

@app.get("/api/alerts")
def list_alerts(
    acknowledged: Optional[bool] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """List price alerts"""
    query = db.query(PriceAlert)
    
    if acknowledged is not None:
        query = query.filter(PriceAlert.is_acknowledged == acknowledged)
    
    alerts = query.order_by(PriceAlert.created_at.desc()).limit(limit).all()
    return alerts

@app.put("/api/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    """Acknowledge a price alert"""
    alert = db.query(PriceAlert).filter(PriceAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.is_acknowledged = True
    alert.acknowledged_at = datetime.now()
    db.commit()
    return {"message": "Alert acknowledged"}


# ==================== HELPER FUNCTIONS ====================

def _update_product_catalog(db: Session, item: InvoiceItemCreate, vendor_id: int, invoice_date: date):
    """Update product catalog with new price data"""
    normalized = item.product_name.lower().strip()
    
    product = db.query(Product).filter(Product.normalized_name == normalized).first()
    
    if product:
        old_price = float(product.last_price) if product.last_price else None
        new_price = item.unit_price
        
        # Check for price change
        if old_price and abs(old_price - new_price) / old_price > 0.05:  # 5% change threshold
            change_pct = ((new_price - old_price) / old_price) * 100
            alert = PriceAlert(
                product_id=product.id,
                vendor_id=vendor_id,
                previous_price=old_price,
                new_price=new_price,
                change_percent=change_pct,
                alert_type='increase' if change_pct > 0 else 'decrease'
            )
            db.add(alert)
        
        # Update product
        product.last_price = new_price
        product.last_vendor_id = vendor_id
        
        # Update min/max
        if not product.min_price or new_price < float(product.min_price):
            product.min_price = new_price
        if not product.max_price or new_price > float(product.max_price):
            product.max_price = new_price
    else:
        # New product
        product = Product(
            name=item.product_name,
            normalized_name=normalized,
            last_vendor_id=vendor_id,
            last_price=item.unit_price,
            min_price=item.unit_price,
            max_price=item.unit_price
        )
        db.add(product)


# ==================== SEED DATA ====================

@app.post("/api/seed")
def seed_database(db: Session = Depends(get_db)):
    """Seed database with initial categories and sample vendor"""
    # Check if already seeded
    if db.query(Category).count() > 0:
        return {"message": "Database already seeded"}
    
    # Add categories
    categories = [
        Category(name="Grocery/Dry Goods", description="Krasdale, shelf-stable items", target_budget_percent=35),
        Category(name="Deli/Specialty", description="Deli items, specialty snacks, wellness", target_budget_percent=10),
        Category(name="Dairy", description="Milk, eggs, cheese, yogurt", target_budget_percent=12),
        Category(name="Frozen", description="Frozen foods, ice cream", target_budget_percent=8),
        Category(name="Beverages", description="Sodas, juices, water", target_budget_percent=10),
        Category(name="Produce", description="Fresh fruits and vegetables", target_budget_percent=15),
        Category(name="Meat/Seafood", description="Fresh and packaged meats", target_budget_percent=8),
        Category(name="Bakery", description="Bread, pastries", target_budget_percent=2),
    ]
    
    for cat in categories:
        db.add(cat)
    db.commit()
    
    # Get Deli/Specialty category
    deli_cat = db.query(Category).filter(Category.name == "Deli/Specialty").first()
    
    # Add sample vendor (SJ Wellness)
    vendor = Vendor(
        name="SJ Wellness",
        category_id=deli_cat.id,
        address="2 Atwood Rd, Plainview 11803",
        phone="7189624504",
        email="jimmychoi138@gmail.com"
    )
    db.add(vendor)
    db.commit()
    
    return {"message": "Database seeded successfully"}


# ==================== STARTUP ====================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    db = SessionLocal()
    try:
        # Auto-seed if empty
        if db.query(Category).count() == 0:
            seed_database(db)
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
