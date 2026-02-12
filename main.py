"""
Apple Tree Purchase Tracker - FastAPI Backend
"""

import os
import io
import csv
import shutil
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, func, extract, desc, case, text
from sqlalchemy.orm import sessionmaker, Session

from models import (
    Base, Category, Vendor, Invoice, InvoiceItem,
    Product, DailySales, MonthlyBudget, PriceAlert,
    ProductVendorPrice, CompetitorStore, CompetitorPrice, Recommendation,
    OCRCorrection, PriceContract,
    DeliInventory, VendorDeliverySchedule, DeliOrderSheet,
)
from ocr_processor import InvoiceOCRProcessor, ExtractedInvoice
from auth import verify_pin, create_token, verify_token

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./purchase_tracker.db")
UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
BACKUP_DIR = Path("./backups")
BACKUP_DIR.mkdir(exist_ok=True)

# Auto-backup: copy DB before doing anything (protects against corruption)
def _backup_database():
    db_path = Path("./purchase_tracker.db")
    if db_path.exists() and db_path.stat().st_size > 0:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"purchase_tracker_{timestamp}.db"
        shutil.copy2(str(db_path), str(backup_path))
        # Keep only last 10 backups
        backups = sorted(BACKUP_DIR.glob("purchase_tracker_*.db"))
        for old in backups[:-10]:
            old.unlink()
        print(f"Database backed up to {backup_path}")

if "sqlite" in DATABASE_URL:
    _backup_database()

# Database setup
connect_args = {}
if "sqlite" in DATABASE_URL:
    connect_args["check_same_thread"] = False
engine = create_engine(DATABASE_URL, connect_args=connect_args)

# Enable WAL mode for SQLite (crash-resilient, survives power loss)
if "sqlite" in DATABASE_URL:
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI
app = FastAPI(
    title="Apple Tree Purchase Tracker",
    description="Track vendor invoices, manage purchasing budgets, and analyze spending",
    version="2.0.0"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# Serve frontend static files (App.jsx, etc.)
FRONTEND_DIR = Path("./frontend")
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend_static")

# Initialize OCR processor
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    print("WARNING: ANTHROPIC_API_KEY not set. OCR will not work.")

ocr_processor = InvoiceOCRProcessor()


# ==================== AUTH MIDDLEWARE ====================

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Block all /api/ routes without a valid Bearer token, except auth endpoints."""
    path = request.url.path

    # Skip auth for non-API routes, auth endpoints, and OPTIONS (CORS preflight)
    if (
        not path.startswith("/api/")
        or path.startswith("/api/auth/")
        or request.method == "OPTIONS"
    ):
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if verify_token(token):
            return await call_next(request)

    return JSONResponse(status_code=401, content={"detail": "Unauthorized"})


# Dependency for database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== PYDANTIC MODELS ====================

class PinLogin(BaseModel):
    pin: str

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
    category_override: Optional[int] = None

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

class CompetitorStoreCreate(BaseModel):
    name: str
    website_url: Optional[str] = None
    scraper_type: str = 'manual'
    scraper_config: Optional[dict] = None

class ManualCompetitorPriceCreate(BaseModel):
    store_id: int
    product_name: str
    price: float
    unit: Optional[str] = None

class ShortageUpdate(BaseModel):
    items: List[dict]  # [{item_id: int, received_quantity: float}]

class ProductSellPriceUpdate(BaseModel):
    sell_price: float
    units_per_case: Optional[int] = None
    target_margin: Optional[float] = None

class PriceContractCreate(BaseModel):
    vendor_id: int
    product_id: int
    agreed_price: float
    start_date: date
    end_date: date
    notes: Optional[str] = None

class OCRCorrectionCreate(BaseModel):
    original_text: str
    corrected_text: str
    field_type: str = 'product_name'

class DisputeCreate(BaseModel):
    invoice_id: int
    reason: str
    item_ids: List[int] = []  # Specific items to dispute


# ==================== AUTH ENDPOINTS ====================

@app.post("/api/auth/login")
def login(body: PinLogin):
    """Verify PIN and return a Bearer token."""
    if not verify_pin(body.pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    token = create_token()
    return {"token": token}

@app.get("/api/auth/verify")
def verify_auth(request: Request):
    """Verify the current token is still valid."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if verify_token(token):
            return {"valid": True}
    raise HTTPException(status_code=401, detail="Invalid or expired token")


# ==================== CATEGORY ENDPOINTS ====================

@app.get("/api/categories", response_model=List[CategoryResponse])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).all()

@app.post("/api/categories", response_model=CategoryResponse)
def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    db_category = Category(**category.dict())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@app.get("/api/categories/{category_id}")
def get_category(category_id: int, db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

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


@app.put("/api/categories/{category_id}")
def update_category(category_id: int, data: CategoryCreate, db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    category.name = data.name
    if data.description is not None:
        category.description = data.description
    if data.target_budget_percent is not None:
        category.target_budget_percent = data.target_budget_percent
    db.commit()
    db.refresh(category)
    return {"id": category.id, "name": category.name, "description": category.description}


@app.get("/api/categories/with-products")
def categories_with_products(db: Session = Depends(get_db)):
    """Categories with product counts and uncategorized count."""
    cats = db.query(Category).all()
    result = []
    for cat in cats:
        count = db.query(func.count(Product.id)).filter(Product.category_id == cat.id).scalar() or 0
        result.append({
            "id": cat.id,
            "name": cat.name,
            "description": cat.description,
            "product_count": count,
        })
    uncategorized = db.query(func.count(Product.id)).filter(Product.category_id == None).scalar() or 0
    return {"categories": result, "uncategorized_count": uncategorized}


@app.get("/api/products/uncategorized")
def uncategorized_products(limit: int = 50, db: Session = Depends(get_db)):
    """Products without a category."""
    products = db.query(Product).filter(Product.category_id == None).limit(limit).all()
    return [
        {"id": p.id, "name": p.name, "last_price": float(p.last_price) if p.last_price else None}
        for p in products
    ]


@app.put("/api/products/{product_id}/category")
def set_product_category(product_id: int, category_id: int, db: Session = Depends(get_db)):
    """Manually assign a category to a product."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.category_id = category_id
    db.commit()
    return {"message": "Category updated", "product_id": product_id, "category_id": category_id}


class BulkCategorizeRequest(BaseModel):
    assignments: List[dict]  # [{product_id: int, category_id: int}]

@app.put("/api/products/bulk-categorize")
def bulk_categorize_products(data: BulkCategorizeRequest, db: Session = Depends(get_db)):
    """Batch assign categories to products."""
    updated = 0
    for entry in data.assignments:
        product = db.query(Product).filter(Product.id == entry.get('product_id')).first()
        if product:
            product.category_id = entry.get('category_id')
            updated += 1
    db.commit()
    return {"message": f"Updated {updated} products"}


@app.post("/api/admin/seed-categories")
def seed_additional_categories(db: Session = Depends(get_db)):
    """Add missing default categories to existing databases."""
    new_cats = [
        ("Snacks/Chips", "Chips, pretzels, crackers, snack foods", 5.0),
        ("Candy/Chocolate", "Candy bars, chocolate, sweets, gummies", 5.0),
        ("Paper Goods", "Paper towels, napkins, plates, cups", 3.0),
        ("Cleaning", "Cleaning supplies, trash bags, detergent", 2.0),
    ]
    added = 0
    for name, desc, pct in new_cats:
        existing = db.query(Category).filter(Category.name == name).first()
        if not existing:
            db.add(Category(name=name, description=desc, target_budget_percent=pct))
            added += 1
    db.commit()
    return {"message": f"Added {added} new categories"}


# ==================== AUTO-CATEGORIZATION ====================

CATEGORY_KEYWORDS = {
    "Snacks/Chips": ["doritos", "lays", "cheetos", "pringles", "fritos", "tostitos", "chip", "pretzel", "popcorn", "crackers", "goldfish", "cheez-it", "ruffles", "kettle", "pirate", "cape cod"],
    "Candy/Chocolate": ["hershey", "snickers", "twix", "m&m", "reese", "kit kat", "milky way", "skittles", "starburst", "gummy", "haribo", "sour patch", "candy", "chocolate", "choco", "tootsie", "nerds", "airheads", "jolly rancher", "nutella", "bueno", "ferrero", "lindt"],
    "Beverages": ["coca-cola", "pepsi", "sprite", "fanta", "gatorade", "snapple", "arizona", "poland spring", "dasani", "redbull", "monster", "juice", "soda", "water", "tea", "coffee", "drink", "lemonade", "tropicana"],
    "Dairy": ["milk", "cheese", "yogurt", "butter", "cream", "egg", "dannon", "chobani", "yoplait", "horizon", "cabot", "sour cream", "cottage"],
    "Produce": ["apple", "banana", "orange", "lettuce", "tomato", "onion", "potato", "carrot", "pepper", "celery", "grape", "melon", "berry", "avocado", "lemon", "lime", "cucumber"],
    "Meat/Seafood": ["beef", "chicken", "pork", "turkey", "ham", "salami", "bacon", "sausage", "hot dog", "shrimp", "salmon", "tuna", "crab", "fish", "steak", "ground meat"],
    "Bakery": ["bread", "roll", "bagel", "muffin", "croissant", "cake", "pie", "donut", "pastry", "baguette", "tortilla", "pita"],
    "Frozen": ["frozen", "ice cream", "pizza frozen", "lean cuisine", "stouffer", "hot pocket", "eggo", "totino"],
    "Grocery/Dry Goods": ["rice", "pasta", "cereal", "soup", "canned", "beans", "flour", "sugar", "oil", "sauce", "ketchup", "mustard", "mayo", "salt", "spice", "seasoning"],
    "Deli/Specialty": ["deli", "hummus", "pesto", "olive", "balsamic", "specialty", "organic", "protein bar", "quest", "barebell", "kind bar", "cliff", "rxbar", "wellness"],
    "Paper Goods": ["paper towel", "napkin", "toilet paper", "tissue", "plate", "cup", "straw", "plastic wrap", "foil", "trash bag"],
    "Cleaning": ["cleaner", "windex", "lysol", "bleach", "detergent", "soap", "mop", "broom", "sponge", "sanitizer"],
}


def auto_categorize_product(product_name: str, db: Session) -> Optional[int]:
    """Match product name to a category using keyword lookup."""
    name_lower = product_name.lower()
    for cat_name, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in name_lower:
                category = db.query(Category).filter(Category.name == cat_name).first()
                if category:
                    return category.id
    return None


# ==================== VENDOR ENDPOINTS ====================

@app.get("/api/vendors")
def list_vendors(
    category_id: Optional[int] = None,
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    query = db.query(Vendor)
    if category_id:
        query = query.filter(Vendor.category_id == category_id)
    if active_only:
        query = query.filter(Vendor.is_active == True)
    vendors = query.all()
    return [v.to_dict() for v in vendors]

@app.post("/api/vendors")
def create_vendor(vendor: VendorCreate, db: Session = Depends(get_db)):
    db_vendor = Vendor(**vendor.dict())
    db.add(db_vendor)
    db.commit()
    db.refresh(db_vendor)
    return db_vendor.to_dict()

@app.get("/api/vendors/{vendor_id}")
def get_vendor(vendor_id: int, db: Session = Depends(get_db)):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    recent_invoices = db.query(Invoice).filter(
        Invoice.vendor_id == vendor_id
    ).order_by(Invoice.invoice_date.desc()).limit(10).all()

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
    vendor = db.query(Vendor).filter(Vendor.id == invoice.vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    # Duplicate invoice detection
    if invoice.invoice_number:
        existing = db.query(Invoice).filter(
            Invoice.vendor_id == invoice.vendor_id,
            Invoice.invoice_number == invoice.invoice_number,
        ).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate invoice: {invoice.invoice_number} from {vendor.name} already exists (Invoice #{existing.id})"
            )

    # Also check for same vendor + same total + same date (possible duplicate without invoice number)
    if not invoice.invoice_number:
        same_day = db.query(Invoice).filter(
            Invoice.vendor_id == invoice.vendor_id,
            Invoice.invoice_date == invoice.invoice_date,
            Invoice.total == invoice.total,
        ).first()
        if same_day:
            raise HTTPException(
                status_code=409,
                detail=f"Possible duplicate: Invoice from {vendor.name} for {invoice.total} on {invoice.invoice_date} already exists (Invoice #{same_day.id}). Add an invoice number to differentiate."
            )

    # Auto-calculate due_date from vendor payment terms
    due_date = None
    if vendor.default_due_days:
        due_date = invoice.invoice_date + timedelta(days=vendor.default_due_days)

    db_invoice = Invoice(
        vendor_id=invoice.vendor_id,
        invoice_number=invoice.invoice_number,
        invoice_date=invoice.invoice_date,
        received_date=invoice.received_date,
        due_date=due_date,
        total=invoice.total,
        tax=invoice.tax,
        notes=invoice.notes
    )
    db.add(db_invoice)
    db.flush()

    for item in invoice.items:
        db_item = InvoiceItem(
            invoice_id=db_invoice.id,
            product_name=item.product_name,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=item.total_price,
            unit=item.unit,
            product_code=item.product_code,
            category_override=item.category_override,
        )
        db.add(db_item)
        db.flush()

        _update_product_catalog(db, item, vendor.id, invoice.invoice_date, db_item.id)

    db.commit()
    db.refresh(db_invoice)

    # Auto-generate recommendations after invoice save
    try:
        from recommendations import RecommendationEngine
        engine = RecommendationEngine(db)
        engine.generate_all()
    except Exception as e:
        print(f"Recommendation generation error: {e}")

    return db_invoice.to_dict(include_items=True)

@app.get("/api/invoices/{invoice_id}")
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice.to_dict(include_items=True)

@app.put("/api/invoices/{invoice_id}/status")
def update_invoice_status(invoice_id: int, status: str, db: Session = Depends(get_db)):
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
    allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'application/pdf']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"File type not allowed. Must be: {allowed_types}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    file_path = UPLOAD_DIR / filename

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = ocr_processor.process_image(str(file_path))
    except Exception as e:
        return OCRResultResponse(
            vendor_name=None, vendor_address=None, vendor_phone=None,
            vendor_email=None, invoice_number=None, invoice_date=None,
            total=None, line_items=[], confidence_score=0.0, suggested_vendor_id=None
        )

    suggested_vendor_id = None
    if result.vendor_name:
        vendor = db.query(Vendor).filter(
            Vendor.name.ilike(f"%{result.vendor_name}%")
        ).first()
        if vendor:
            suggested_vendor_id = vendor.id

    line_items = [{
        'product_name': item.product_name,
        'quantity': item.quantity,
        'unit_price': item.unit_price,
        'total_price': item.total_price
    } for item in result.line_items]

    # Apply learned OCR corrections
    line_items = apply_ocr_corrections(db, line_items)

    return OCRResultResponse(
        vendor_name=result.vendor_name,
        vendor_address=result.vendor_address,
        vendor_phone=result.vendor_phone,
        vendor_email=result.vendor_email,
        invoice_number=result.invoice_number,
        invoice_date=result.invoice_date,
        total=result.total,
        line_items=line_items,
        confidence_score=result.confidence_score,
        suggested_vendor_id=suggested_vendor_id
    )


@app.post("/api/ocr/process-multi", response_model=OCRResultResponse)
async def process_multi_invoice_images(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """Process multiple invoice page images in a single OCR call."""
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 pages allowed")

    allowed_types = ['image/jpeg', 'image/png', 'image/jpg']
    images = []
    for f in files:
        if f.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"File type not allowed: {f.content_type}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{f.filename}"
        file_path = UPLOAD_DIR / filename
        content = await f.read()
        with open(file_path, "wb") as out:
            out.write(content)
        suffix = Path(f.filename).suffix.lower() if f.filename else '.jpg'
        images.append((content, suffix))

    try:
        result = ocr_processor.process_multiple_images(images)
    except Exception as e:
        return OCRResultResponse(
            vendor_name=None, vendor_address=None, vendor_phone=None,
            vendor_email=None, invoice_number=None, invoice_date=None,
            total=None, line_items=[], confidence_score=0.0, suggested_vendor_id=None
        )

    suggested_vendor_id = None
    if result.vendor_name:
        vendor = db.query(Vendor).filter(
            Vendor.name.ilike(f"%{result.vendor_name}%")
        ).first()
        if vendor:
            suggested_vendor_id = vendor.id

    line_items = [{
        'product_name': item.product_name,
        'quantity': item.quantity,
        'unit_price': item.unit_price,
        'total_price': item.total_price
    } for item in result.line_items]

    line_items = apply_ocr_corrections(db, line_items)

    return OCRResultResponse(
        vendor_name=result.vendor_name,
        vendor_address=result.vendor_address,
        vendor_phone=result.vendor_phone,
        vendor_email=result.vendor_email,
        invoice_number=result.invoice_number,
        invoice_date=result.invoice_date,
        total=result.total,
        line_items=line_items,
        confidence_score=result.confidence_score,
        suggested_vendor_id=suggested_vendor_id
    )


# ==================== DASHBOARD/ANALYTICS ENDPOINTS ====================

@app.get("/api/dashboard/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    now = datetime.now()
    today = date.today()
    month_start = date(now.year, now.month, 1)
    week_start = today - timedelta(days=today.weekday())

    today_total = db.query(func.sum(Invoice.total)).filter(
        Invoice.invoice_date == today
    ).scalar() or 0

    week_total = db.query(func.sum(Invoice.total)).filter(
        Invoice.invoice_date >= week_start
    ).scalar() or 0

    month_total = db.query(func.sum(Invoice.total)).filter(
        Invoice.invoice_date >= month_start
    ).scalar() or 0

    pending_count = db.query(func.count(Invoice.id)).filter(
        Invoice.status == 'pending'
    ).scalar() or 0

    recent_invoices = db.query(Invoice).order_by(
        Invoice.created_at.desc()
    ).limit(5).all()

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
    now = datetime.now()
    month_start = date(now.year, now.month, 1)

    monthly_sales = db.query(func.sum(DailySales.gross_sales)).filter(
        DailySales.sale_date >= month_start
    ).scalar() or 0

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


# ==================== ANALYTICS ENDPOINTS (Phase 3) ====================

@app.get("/api/analytics/products")
def analytics_products(
    sort_by: str = Query(default="spend", enum=["spend", "volume", "price_change"]),
    limit: int = Query(default=50, le=200),
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Products sorted by spend, volume, or price change."""
    cutoff_90 = date.today() - timedelta(days=90)

    query = db.query(
        Product.id,
        Product.name,
        Product.last_price,
        Product.avg_price,
        Product.min_price,
        Product.max_price,
        Product.sell_price,
        Product.units_per_case,
        Product.target_margin,
        Product.category_id,
        func.sum(ProductVendorPrice.quantity).label('total_volume'),
        func.sum(ProductVendorPrice.unit_price * ProductVendorPrice.quantity).label('total_spend'),
        func.count(func.distinct(ProductVendorPrice.vendor_id)).label('vendor_count'),
    ).outerjoin(ProductVendorPrice, ProductVendorPrice.product_id == Product.id
    ).filter(
        (ProductVendorPrice.invoice_date >= cutoff_90) | (ProductVendorPrice.id == None)
    )

    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))

    query = query.group_by(Product.id)

    if sort_by == "spend":
        query = query.order_by(desc(func.sum(ProductVendorPrice.unit_price * ProductVendorPrice.quantity)))
    elif sort_by == "volume":
        query = query.order_by(desc(func.sum(ProductVendorPrice.quantity)))
    else:
        query = query.order_by(desc(Product.max_price - Product.min_price))

    rows = query.limit(limit).all()

    # Build category name lookup
    cat_map = {c.id: c.name for c in db.query(Category).all()}

    return [
        {
            "id": r.id,
            "name": r.name,
            "last_price": float(r.last_price) if r.last_price else None,
            "avg_price": float(r.avg_price) if r.avg_price else None,
            "min_price": float(r.min_price) if r.min_price else None,
            "max_price": float(r.max_price) if r.max_price else None,
            "sell_price": float(r.sell_price) if r.sell_price else None,
            "units_per_case": r.units_per_case,
            "target_margin": float(r.target_margin) if r.target_margin else None,
            "category_id": r.category_id,
            "category_name": cat_map.get(r.category_id) if r.category_id else None,
            "total_volume": float(r.total_volume) if r.total_volume else 0,
            "total_spend": float(r.total_spend) if r.total_spend else 0,
            "vendor_count": r.vendor_count or 0,
        }
        for r in rows
    ]

@app.get("/api/analytics/products/{product_id}/price-history")
def product_price_history(product_id: int, days: int = 90, db: Session = Depends(get_db)):
    """Price data points for a specific product, grouped by vendor."""
    cutoff = date.today() - timedelta(days=days)

    rows = db.query(
        ProductVendorPrice.invoice_date,
        ProductVendorPrice.unit_price,
        ProductVendorPrice.quantity,
        Vendor.id.label('vendor_id'),
        Vendor.name.label('vendor_name'),
    ).join(Vendor, Vendor.id == ProductVendorPrice.vendor_id
    ).filter(
        ProductVendorPrice.product_id == product_id,
        ProductVendorPrice.invoice_date >= cutoff,
    ).order_by(ProductVendorPrice.invoice_date).all()

    return [
        {
            "date": r.invoice_date.isoformat(),
            "price": float(r.unit_price),
            "quantity": float(r.quantity) if r.quantity else None,
            "vendor_id": r.vendor_id,
            "vendor_name": r.vendor_name,
        }
        for r in rows
    ]

@app.get("/api/analytics/products/{product_id}/vendors")
def product_vendors(product_id: int, db: Session = Depends(get_db)):
    """Same product across all vendors with avg price and last price."""
    cutoff = date.today() - timedelta(days=90)

    rows = db.query(
        Vendor.id,
        Vendor.name,
        func.avg(ProductVendorPrice.unit_price).label('avg_price'),
        func.min(ProductVendorPrice.unit_price).label('min_price'),
        func.max(ProductVendorPrice.unit_price).label('max_price'),
        func.count(ProductVendorPrice.id).label('purchase_count'),
    ).join(ProductVendorPrice, ProductVendorPrice.vendor_id == Vendor.id
    ).filter(
        ProductVendorPrice.product_id == product_id,
        ProductVendorPrice.invoice_date >= cutoff,
    ).group_by(Vendor.id).order_by(func.avg(ProductVendorPrice.unit_price)).all()

    return [
        {
            "vendor_id": r.id,
            "vendor_name": r.name,
            "avg_price": round(float(r.avg_price), 2),
            "min_price": float(r.min_price),
            "max_price": float(r.max_price),
            "purchase_count": r.purchase_count,
        }
        for r in rows
    ]

@app.get("/api/analytics/volume-trends")
def volume_trends(limit: int = 20, db: Session = Depends(get_db)):
    """Top products by purchase volume with trend direction."""
    recent_cutoff = date.today() - timedelta(days=30)
    prev_cutoff = date.today() - timedelta(days=60)

    recent = db.query(
        ProductVendorPrice.product_id,
        func.sum(ProductVendorPrice.quantity).label('recent_vol'),
    ).filter(
        ProductVendorPrice.invoice_date >= recent_cutoff,
    ).group_by(ProductVendorPrice.product_id).subquery()

    previous = db.query(
        ProductVendorPrice.product_id,
        func.sum(ProductVendorPrice.quantity).label('prev_vol'),
    ).filter(
        ProductVendorPrice.invoice_date >= prev_cutoff,
        ProductVendorPrice.invoice_date < recent_cutoff,
    ).group_by(ProductVendorPrice.product_id).subquery()

    rows = db.query(
        Product.id,
        Product.name,
        recent.c.recent_vol,
        previous.c.prev_vol,
    ).join(recent, recent.c.product_id == Product.id
    ).outerjoin(previous, previous.c.product_id == Product.id
    ).order_by(desc(recent.c.recent_vol)).limit(limit).all()

    return [
        {
            "id": r.id,
            "name": r.name,
            "recent_volume": float(r.recent_vol) if r.recent_vol else 0,
            "previous_volume": float(r.prev_vol) if r.prev_vol else 0,
            "trend": "up" if r.prev_vol and r.recent_vol and float(r.recent_vol) > float(r.prev_vol) * 1.1
                     else "down" if r.prev_vol and r.recent_vol and float(r.recent_vol) < float(r.prev_vol) * 0.9
                     else "stable",
        }
        for r in rows
    ]

@app.get("/api/analytics/vendor-comparison")
def vendor_comparison(db: Session = Depends(get_db)):
    """Vendor performance comparison."""
    cutoff = date.today() - timedelta(days=90)

    rows = db.query(
        Vendor.id,
        Vendor.name,
        func.count(func.distinct(Invoice.id)).label('invoice_count'),
        func.sum(Invoice.total).label('total_spend'),
        func.count(func.distinct(ProductVendorPrice.product_id)).label('product_count'),
        func.avg(ProductVendorPrice.unit_price).label('avg_unit_price'),
    ).outerjoin(Invoice, (Invoice.vendor_id == Vendor.id) & (Invoice.invoice_date >= cutoff)
    ).outerjoin(ProductVendorPrice, (ProductVendorPrice.vendor_id == Vendor.id) & (ProductVendorPrice.invoice_date >= cutoff)
    ).filter(Vendor.is_active == True
    ).group_by(Vendor.id).order_by(desc(func.sum(Invoice.total))).all()

    return [
        {
            "vendor_id": r.id,
            "vendor_name": r.name,
            "invoice_count": r.invoice_count or 0,
            "total_spend": float(r.total_spend) if r.total_spend else 0,
            "product_count": r.product_count or 0,
            "avg_unit_price": round(float(r.avg_unit_price), 2) if r.avg_unit_price else 0,
        }
        for r in rows
    ]

@app.get("/api/analytics/spending-by-product")
def spending_by_product(limit: int = 20, db: Session = Depends(get_db)):
    """Top products by total spend."""
    cutoff = date.today() - timedelta(days=90)

    rows = db.query(
        Product.id,
        Product.name,
        func.sum(ProductVendorPrice.unit_price * ProductVendorPrice.quantity).label('total_spend'),
        func.sum(ProductVendorPrice.quantity).label('total_quantity'),
    ).join(ProductVendorPrice, ProductVendorPrice.product_id == Product.id
    ).filter(ProductVendorPrice.invoice_date >= cutoff
    ).group_by(Product.id
    ).order_by(desc(func.sum(ProductVendorPrice.unit_price * ProductVendorPrice.quantity))
    ).limit(limit).all()

    return [
        {
            "id": r.id,
            "name": r.name,
            "total_spend": float(r.total_spend) if r.total_spend else 0,
            "total_quantity": float(r.total_quantity) if r.total_quantity else 0,
        }
        for r in rows
    ]

@app.get("/api/analytics/price-alerts-summary")
def price_alerts_summary(db: Session = Depends(get_db)):
    """Unacknowledged alerts with context."""
    alerts = db.query(PriceAlert).filter(
        PriceAlert.is_acknowledged == False
    ).order_by(PriceAlert.created_at.desc()).limit(20).all()

    result = []
    for alert in alerts:
        product = db.query(Product).get(alert.product_id) if alert.product_id else None
        vendor = db.query(Vendor).get(alert.vendor_id) if alert.vendor_id else None
        result.append({
            "id": alert.id,
            "product_name": product.name if product else "Unknown",
            "vendor_name": vendor.name if vendor else "Unknown",
            "previous_price": float(alert.previous_price) if alert.previous_price else None,
            "new_price": float(alert.new_price) if alert.new_price else None,
            "change_percent": float(alert.change_percent) if alert.change_percent else None,
            "alert_type": alert.alert_type,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
        })

    return {"count": len(result), "alerts": result}


# ==================== BACKFILL ENDPOINT (Phase 3) ====================

@app.post("/api/admin/backfill-price-data")
def backfill_price_data(db: Session = Depends(get_db)):
    """Backfill product_vendor_prices from existing invoice data."""
    existing_count = db.query(ProductVendorPrice).count()
    if existing_count > 0:
        return {"message": f"Already have {existing_count} price records. Skipping backfill."}

    invoices = db.query(Invoice).all()
    count = 0

    for invoice in invoices:
        for item in invoice.items:
            normalized = item.product_name.lower().strip()
            product = db.query(Product).filter(Product.normalized_name == normalized).first()

            if not product:
                product = Product(
                    name=item.product_name,
                    normalized_name=normalized,
                    last_vendor_id=invoice.vendor_id,
                    last_price=float(item.unit_price),
                    min_price=float(item.unit_price),
                    max_price=float(item.unit_price),
                )
                db.add(product)
                db.flush()

            pvp = ProductVendorPrice(
                product_id=product.id,
                vendor_id=invoice.vendor_id,
                invoice_item_id=item.id,
                invoice_date=invoice.invoice_date,
                unit_price=float(item.unit_price),
                quantity=float(item.quantity) if item.quantity else 1,
                unit=item.unit,
            )
            db.add(pvp)
            count += 1

    # Update product avg prices
    for product in db.query(Product).all():
        prices = db.query(ProductVendorPrice.unit_price).filter(
            ProductVendorPrice.product_id == product.id
        ).all()
        if prices:
            price_vals = [float(p[0]) for p in prices]
            product.avg_price = sum(price_vals) / len(price_vals)
            product.min_price = min(price_vals)
            product.max_price = max(price_vals)
            # Update price_history JSON
            history = db.query(
                ProductVendorPrice.invoice_date,
                ProductVendorPrice.unit_price,
                ProductVendorPrice.vendor_id,
            ).filter(ProductVendorPrice.product_id == product.id
            ).order_by(ProductVendorPrice.invoice_date).all()
            product.price_history = [
                {"date": h.invoice_date.isoformat(), "price": float(h.unit_price), "vendor_id": h.vendor_id}
                for h in history
            ]

    db.commit()
    return {"message": f"Backfilled {count} price records"}


# ==================== DAILY SALES ENDPOINTS ====================

@app.get("/api/sales")
def list_sales(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 30,
    db: Session = Depends(get_db)
):
    query = db.query(DailySales)
    if start_date:
        query = query.filter(DailySales.sale_date >= start_date)
    if end_date:
        query = query.filter(DailySales.sale_date <= end_date)
    sales = query.order_by(DailySales.sale_date.desc()).limit(limit).all()
    return [s.to_dict() for s in sales]

@app.post("/api/sales")
def create_sales(sales: DailySalesCreate, db: Session = Depends(get_db)):
    existing = db.query(DailySales).filter(DailySales.sale_date == sales.sale_date).first()
    if existing:
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
    query = db.query(PriceAlert)
    if acknowledged is not None:
        query = query.filter(PriceAlert.is_acknowledged == acknowledged)
    alerts = query.order_by(PriceAlert.created_at.desc()).limit(limit).all()
    return alerts

@app.put("/api/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(PriceAlert).filter(PriceAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.is_acknowledged = True
    alert.acknowledged_at = datetime.now()
    db.commit()
    return {"message": "Alert acknowledged"}


# ==================== COMPETITOR ENDPOINTS (Phase 4) ====================

@app.get("/api/competitors")
def list_competitors(db: Session = Depends(get_db)):
    stores = db.query(CompetitorStore).filter(CompetitorStore.is_active == True).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "website_url": s.website_url,
            "scraper_type": s.scraper_type,
            "last_scraped_at": s.last_scraped_at.isoformat() if s.last_scraped_at else None,
        }
        for s in stores
    ]

@app.post("/api/competitors")
def create_competitor(store: CompetitorStoreCreate, db: Session = Depends(get_db)):
    db_store = CompetitorStore(
        name=store.name,
        website_url=store.website_url,
        scraper_type=store.scraper_type,
        scraper_config=store.scraper_config,
    )
    db.add(db_store)
    db.commit()
    db.refresh(db_store)
    return {
        "id": db_store.id,
        "name": db_store.name,
        "website_url": db_store.website_url,
        "scraper_type": db_store.scraper_type,
    }

@app.post("/api/competitors/{store_id}/scrape")
async def trigger_scrape(store_id: int, db: Session = Depends(get_db)):
    store = db.query(CompetitorStore).filter(CompetitorStore.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    from scraper import run_scraper
    count = await run_scraper(store, db)
    return {"message": f"Scraped {count} prices from {store.name}"}

@app.get("/api/competitors/prices")
def competitor_prices(
    product_id: Optional[int] = None,
    store_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(CompetitorPrice).filter(CompetitorPrice.is_current == True)
    if product_id:
        query = query.filter(CompetitorPrice.matched_product_id == product_id)
    if store_id:
        query = query.filter(CompetitorPrice.store_id == store_id)

    prices = query.all()
    return [
        {
            "id": p.id,
            "store_id": p.store_id,
            "store_name": p.store.name if p.store else None,
            "product_name": p.product_name,
            "matched_product_id": p.matched_product_id,
            "price": float(p.price),
            "unit": p.unit,
            "scraped_at": p.scraped_at.isoformat() if p.scraped_at else None,
        }
        for p in prices
    ]

@app.post("/api/competitors/prices/manual")
def add_manual_competitor_price(entry: ManualCompetitorPriceCreate, db: Session = Depends(get_db)):
    store = db.query(CompetitorStore).filter(CompetitorStore.id == entry.store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    from scraper import normalize_product_name, fuzzy_match_product

    normalized = normalize_product_name(entry.product_name)
    products = db.query(Product).all()
    matched = fuzzy_match_product(entry.product_name, products)

    # Mark previous prices for same store/product as not current
    db.query(CompetitorPrice).filter(
        CompetitorPrice.store_id == entry.store_id,
        CompetitorPrice.normalized_name == normalized,
        CompetitorPrice.is_current == True,
    ).update({CompetitorPrice.is_current: False})

    price = CompetitorPrice(
        store_id=entry.store_id,
        product_name=entry.product_name,
        normalized_name=normalized,
        matched_product_id=matched.id if matched else None,
        price=entry.price,
        unit=entry.unit,
        is_current=True,
    )
    db.add(price)
    db.commit()
    db.refresh(price)

    return {
        "id": price.id,
        "product_name": price.product_name,
        "matched_product_id": price.matched_product_id,
        "price": float(price.price),
    }

@app.get("/api/analytics/savings-opportunities")
def savings_opportunities(db: Session = Depends(get_db)):
    """Products where competitors are cheaper."""
    competitor_prices_q = db.query(CompetitorPrice).filter(
        CompetitorPrice.is_current == True,
        CompetitorPrice.matched_product_id != None,
    ).all()

    opportunities = []
    for cp in competitor_prices_q:
        product = db.query(Product).get(cp.matched_product_id)
        if not product or not product.last_price:
            continue

        our_price = float(product.last_price)
        their_price = float(cp.price)

        if their_price >= our_price:
            continue

        savings_pct = ((our_price - their_price) / our_price) * 100
        store = db.query(CompetitorStore).get(cp.store_id)

        opportunities.append({
            "product_id": product.id,
            "product_name": product.name,
            "our_price": our_price,
            "competitor_price": their_price,
            "competitor_store": store.name if store else "Unknown",
            "savings_percent": round(savings_pct, 1),
            "savings_amount": round(our_price - their_price, 2),
        })

    opportunities.sort(key=lambda x: x['savings_percent'], reverse=True)
    total_savings = sum(o['savings_amount'] for o in opportunities)

    return {
        "total_potential_savings": round(total_savings, 2),
        "opportunities": opportunities,
    }


# ==================== RECOMMENDATION ENDPOINTS (Phase 5) ====================

@app.get("/api/recommendations")
def get_recommendations(db: Session = Depends(get_db)):
    """Active recommendations sorted by priority."""
    recs = db.query(Recommendation).filter(
        Recommendation.is_dismissed == False,
        Recommendation.is_acted_on == False,
    ).order_by(Recommendation.priority, Recommendation.created_at.desc()).all()

    return [
        {
            "id": r.id,
            "type": r.type,
            "product_id": r.product_id,
            "vendor_id": r.vendor_id,
            "title": r.title,
            "description": r.description,
            "potential_savings": float(r.potential_savings) if r.potential_savings else None,
            "priority": r.priority,
            "data": r.data,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in recs
    ]

@app.post("/api/recommendations/generate")
def generate_recommendations(db: Session = Depends(get_db)):
    """Trigger recommendation generation."""
    from recommendations import RecommendationEngine
    engine = RecommendationEngine(db)
    count = engine.generate_all()
    return {"message": f"Generated {count} new recommendations"}

@app.put("/api/recommendations/{rec_id}/dismiss")
def dismiss_recommendation(rec_id: int, db: Session = Depends(get_db)):
    rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    rec.is_dismissed = True
    rec.updated_at = datetime.now()
    db.commit()
    return {"message": "Recommendation dismissed"}

@app.put("/api/recommendations/{rec_id}/acted")
def acted_on_recommendation(rec_id: int, db: Session = Depends(get_db)):
    rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    rec.is_acted_on = True
    rec.updated_at = datetime.now()
    db.commit()
    return {"message": "Recommendation marked as acted on"}


# ==================== SHORTAGE & DELIVERY TRACKING ====================

@app.put("/api/invoices/{invoice_id}/shortages")
def update_shortages(invoice_id: int, data: ShortageUpdate, db: Session = Depends(get_db)):
    """Mark received quantities for invoice items to track shortages."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    total_shortage_value = 0
    for entry in data.items:
        item = db.query(InvoiceItem).filter(
            InvoiceItem.id == entry.get('item_id'),
            InvoiceItem.invoice_id == invoice_id,
        ).first()
        if not item:
            continue
        received = entry.get('received_quantity', float(item.quantity))
        item.received_quantity = received
        shortage_qty = max(0, float(item.quantity) - received)
        total_shortage_value += shortage_qty * float(item.unit_price)

    invoice.has_shortage = total_shortage_value > 0
    invoice.shortage_total = total_shortage_value
    db.commit()

    return {
        "message": f"Shortages updated. Total shortage value: ${total_shortage_value:.2f}",
        "shortage_total": total_shortage_value,
        "has_shortage": total_shortage_value > 0,
    }

@app.get("/api/invoices/shortages")
def list_shortages(db: Session = Depends(get_db)):
    """List all invoices with shortages."""
    invoices = db.query(Invoice).filter(
        Invoice.has_shortage == True
    ).order_by(Invoice.invoice_date.desc()).all()

    result = []
    for inv in invoices:
        shortage_items = [item.to_dict() for item in inv.items if item.received_quantity is not None and float(item.quantity) > float(item.received_quantity)]
        result.append({
            **inv.to_dict(),
            "shortage_items": shortage_items,
        })
    return result


# ==================== DISPUTE TRACKING ====================

@app.post("/api/invoices/dispute")
def create_dispute(data: DisputeCreate, db: Session = Depends(get_db)):
    """Mark an invoice as disputed."""
    invoice = db.query(Invoice).filter(Invoice.id == data.invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    invoice.status = 'disputed'
    invoice.dispute_reason = data.reason
    invoice.dispute_status = 'open'

    for item_id in data.item_ids:
        item = db.query(InvoiceItem).filter(
            InvoiceItem.id == item_id,
            InvoiceItem.invoice_id == data.invoice_id,
        ).first()
        if item:
            item.is_disputed = True
            item.dispute_reason = data.reason

    db.commit()
    return {"message": "Invoice disputed", "invoice": invoice.to_dict(include_items=True)}

@app.put("/api/invoices/{invoice_id}/dispute/resolve")
def resolve_dispute(invoice_id: int, credit_amount: float = 0, db: Session = Depends(get_db)):
    """Resolve a dispute, optionally with a credit amount."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    invoice.dispute_status = 'credited' if credit_amount > 0 else 'resolved'
    invoice.credit_amount = credit_amount
    if credit_amount > 0:
        invoice.status = 'verified'
    db.commit()
    return {"message": f"Dispute resolved. Credit: ${credit_amount:.2f}"}

@app.get("/api/disputes")
def list_disputes(db: Session = Depends(get_db)):
    """List all open disputes."""
    invoices = db.query(Invoice).filter(
        Invoice.dispute_status == 'open'
    ).order_by(Invoice.created_at.desc()).all()
    return [inv.to_dict() for inv in invoices]


# ==================== CSV EXPORT ====================

@app.get("/api/export/invoices")
def export_invoices_csv(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Export invoices as CSV for accounting software."""
    query = db.query(Invoice).join(Vendor)
    if start_date:
        query = query.filter(Invoice.invoice_date >= start_date)
    if end_date:
        query = query.filter(Invoice.invoice_date <= end_date)

    invoices = query.order_by(Invoice.invoice_date).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Invoice Date', 'Vendor', 'Category', 'Invoice #', 'Status',
        'Subtotal', 'Tax', 'Total', 'Due Date', 'Payment Date',
        'Has Shortage', 'Shortage Amount', 'Dispute Status', 'Credit Amount'
    ])

    for inv in invoices:
        writer.writerow([
            inv.invoice_date.isoformat() if inv.invoice_date else '',
            inv.vendor.name if inv.vendor else '',
            inv.vendor.category.name if inv.vendor and inv.vendor.category else '',
            inv.invoice_number or '',
            inv.status,
            float(inv.subtotal) if inv.subtotal else '',
            float(inv.tax) if inv.tax else 0,
            float(inv.total) if inv.total else 0,
            inv.due_date.isoformat() if inv.due_date else '',
            inv.payment_date.isoformat() if inv.payment_date else '',
            'Yes' if inv.has_shortage else 'No',
            float(inv.shortage_total) if inv.shortage_total else 0,
            inv.dispute_status or '',
            float(inv.credit_amount) if inv.credit_amount else 0,
        ])

    output.seek(0)
    filename = f"invoices_{date.today().isoformat()}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/api/export/line-items")
def export_line_items_csv(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Export all line items as CSV."""
    query = db.query(InvoiceItem).join(Invoice).join(Vendor)
    if start_date:
        query = query.filter(Invoice.invoice_date >= start_date)
    if end_date:
        query = query.filter(Invoice.invoice_date <= end_date)

    items = query.order_by(Invoice.invoice_date).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Date', 'Vendor', 'Invoice #', 'Product', 'Product Code',
        'Quantity', 'Received Qty', 'Shortage', 'Unit', 'Unit Price', 'Total Price'
    ])

    for item in items:
        inv = item.invoice
        shortage = 0
        if item.received_quantity is not None and item.quantity:
            shortage = max(0, float(item.quantity) - float(item.received_quantity))
        writer.writerow([
            inv.invoice_date.isoformat() if inv.invoice_date else '',
            inv.vendor.name if inv.vendor else '',
            inv.invoice_number or '',
            item.product_name,
            item.product_code or '',
            float(item.quantity) if item.quantity else 0,
            float(item.received_quantity) if item.received_quantity is not None else '',
            shortage,
            item.unit or '',
            float(item.unit_price) if item.unit_price else 0,
            float(item.total_price) if item.total_price else 0,
        ])

    output.seek(0)
    filename = f"line_items_{date.today().isoformat()}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ==================== PAYMENT DUE DATES / CASH FLOW ====================

@app.get("/api/payments/due")
def payments_due(db: Session = Depends(get_db)):
    """Invoices with upcoming or overdue payment due dates."""
    unpaid = db.query(Invoice).filter(
        Invoice.status.in_(['pending', 'verified']),
        Invoice.due_date != None,
    ).order_by(Invoice.due_date).all()

    today = date.today()
    overdue = []
    due_this_week = []
    due_later = []

    for inv in unpaid:
        entry = {
            **inv.to_dict(),
            "days_until_due": (inv.due_date - today).days,
        }
        if inv.due_date < today:
            overdue.append(entry)
        elif inv.due_date <= today + timedelta(days=7):
            due_this_week.append(entry)
        else:
            due_later.append(entry)

    overdue_total = sum(float(inv.total) for inv in unpaid if inv.due_date and inv.due_date < today)
    week_total = sum(float(inv.total) for inv in unpaid if inv.due_date and today <= inv.due_date <= today + timedelta(days=7))

    return {
        "overdue": overdue,
        "overdue_total": overdue_total,
        "due_this_week": due_this_week,
        "due_this_week_total": week_total,
        "due_later": due_later,
        "total_outstanding": sum(float(inv.total) for inv in unpaid),
    }

@app.get("/api/analytics/cash-flow")
def cash_flow_forecast(days: int = 30, db: Session = Depends(get_db)):
    """Cash flow forecast based on upcoming due dates."""
    today = date.today()
    end = today + timedelta(days=days)

    unpaid = db.query(Invoice).filter(
        Invoice.status.in_(['pending', 'verified']),
        Invoice.due_date != None,
        Invoice.due_date >= today,
        Invoice.due_date <= end,
    ).order_by(Invoice.due_date).all()

    # Group by week
    weeks = {}
    for inv in unpaid:
        week_start = inv.due_date - timedelta(days=inv.due_date.weekday())
        week_key = week_start.isoformat()
        if week_key not in weeks:
            weeks[week_key] = {"week_start": week_key, "total": 0, "count": 0, "vendors": []}
        weeks[week_key]["total"] += float(inv.total)
        weeks[week_key]["count"] += 1
        vname = inv.vendor.name if inv.vendor else "Unknown"
        if vname not in weeks[week_key]["vendors"]:
            weeks[week_key]["vendors"].append(vname)

    return {
        "forecast_days": days,
        "total_due": sum(float(inv.total) for inv in unpaid),
        "invoice_count": len(unpaid),
        "by_week": list(weeks.values()),
    }


# ==================== VENDOR SCORECARD ====================

@app.get("/api/vendors/{vendor_id}/scorecard")
def vendor_scorecard(vendor_id: int, db: Session = Depends(get_db)):
    """Comprehensive vendor performance scorecard."""
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    cutoff = date.today() - timedelta(days=180)

    # Invoice stats
    invoices = db.query(Invoice).filter(
        Invoice.vendor_id == vendor_id,
        Invoice.invoice_date >= cutoff,
    ).all()

    total_invoices = len(invoices)
    total_spent = sum(float(inv.total) for inv in invoices)
    disputed_count = sum(1 for inv in invoices if inv.dispute_status)
    shortage_count = sum(1 for inv in invoices if inv.has_shortage)

    # Price stability: how many price alerts for this vendor
    alert_count = db.query(func.count(PriceAlert.id)).filter(
        PriceAlert.vendor_id == vendor_id,
        PriceAlert.created_at >= cutoff,
    ).scalar() or 0

    increase_count = db.query(func.count(PriceAlert.id)).filter(
        PriceAlert.vendor_id == vendor_id,
        PriceAlert.alert_type == 'increase',
        PriceAlert.created_at >= cutoff,
    ).scalar() or 0

    # Product count
    product_count = db.query(func.count(func.distinct(ProductVendorPrice.product_id))).filter(
        ProductVendorPrice.vendor_id == vendor_id,
    ).scalar() or 0

    # Scores (0-100)
    reliability_score = max(0, 100 - (shortage_count * 15) - (disputed_count * 20))
    price_stability_score = max(0, 100 - (increase_count * 10))
    overall_score = (reliability_score + price_stability_score) // 2

    # Active contracts
    active_contracts = db.query(PriceContract).filter(
        PriceContract.vendor_id == vendor_id,
        PriceContract.is_active == True,
        PriceContract.end_date >= date.today(),
    ).count()

    return {
        "vendor": vendor.to_dict(),
        "period_days": 180,
        "total_invoices": total_invoices,
        "total_spent": total_spent,
        "product_count": product_count,
        "shortage_count": shortage_count,
        "disputed_count": disputed_count,
        "price_alerts": alert_count,
        "price_increases": increase_count,
        "active_contracts": active_contracts,
        "scores": {
            "reliability": reliability_score,
            "price_stability": price_stability_score,
            "overall": overall_score,
        },
    }


# ==================== PROFIT MARGIN TRACKING ====================

@app.put("/api/products/{product_id}/sell-price")
def update_sell_price(product_id: int, data: ProductSellPriceUpdate, db: Session = Depends(get_db)):
    """Set the retail sell price for a product to calculate margins."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.sell_price = data.sell_price
    if data.units_per_case is not None:
        product.units_per_case = data.units_per_case
    if data.target_margin is not None:
        product.target_margin = data.target_margin
    db.commit()

    return {"message": "Sell price updated", "product_id": product_id}

@app.get("/api/analytics/margins")
def profit_margins(db: Session = Depends(get_db)):
    """Products with sell price set, showing buy/sell/margin."""
    products = db.query(Product).filter(
        Product.sell_price != None,
        Product.last_price != None,
    ).all()

    result = []
    for p in products:
        buy = float(p.last_price)
        sell_per_unit = float(p.sell_price)
        units = p.units_per_case or 1
        revenue_per_case = sell_per_unit * units
        margin = ((revenue_per_case - buy) / revenue_per_case) * 100 if revenue_per_case > 0 else 0
        target = float(p.target_margin) if p.target_margin else None

        result.append({
            "id": p.id,
            "name": p.name,
            "buy_price": buy,
            "sell_price": sell_per_unit,
            "units_per_case": units,
            "revenue_per_case": round(revenue_per_case, 2),
            "margin_percent": round(margin, 1),
            "target_margin": target,
            "margin_status": "below" if target and margin < target else "above" if target and margin >= target else "no_target",
        })

    result.sort(key=lambda x: x['margin_percent'])
    return result


# ==================== PRICE CONTRACTS ====================

@app.get("/api/contracts")
def list_contracts(active_only: bool = True, db: Session = Depends(get_db)):
    """List price contracts."""
    query = db.query(PriceContract)
    if active_only:
        query = query.filter(
            PriceContract.is_active == True,
            PriceContract.end_date >= date.today(),
        )

    contracts = query.order_by(PriceContract.end_date).all()
    result = []
    for c in contracts:
        product = db.query(Product).get(c.product_id)
        vendor = db.query(Vendor).get(c.vendor_id)
        days_left = (c.end_date - date.today()).days

        # Check if current price exceeds contract
        violation = False
        if product and product.last_price:
            violation = float(product.last_price) > float(c.agreed_price) * 1.01

        result.append({
            "id": c.id,
            "vendor_name": vendor.name if vendor else "Unknown",
            "product_name": product.name if product else "Unknown",
            "agreed_price": float(c.agreed_price),
            "current_price": float(product.last_price) if product and product.last_price else None,
            "start_date": c.start_date.isoformat(),
            "end_date": c.end_date.isoformat(),
            "days_left": days_left,
            "is_violated": violation,
            "notes": c.notes,
        })
    return result

@app.post("/api/contracts")
def create_contract(data: PriceContractCreate, db: Session = Depends(get_db)):
    """Create a new price contract."""
    contract = PriceContract(
        vendor_id=data.vendor_id,
        product_id=data.product_id,
        agreed_price=data.agreed_price,
        start_date=data.start_date,
        end_date=data.end_date,
        notes=data.notes,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return {"id": contract.id, "message": "Contract created"}

@app.delete("/api/contracts/{contract_id}")
def delete_contract(contract_id: int, db: Session = Depends(get_db)):
    contract = db.query(PriceContract).filter(PriceContract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    contract.is_active = False
    db.commit()
    return {"message": "Contract deactivated"}


# ==================== OCR LEARNING / CORRECTIONS ====================

@app.post("/api/ocr/corrections")
def save_ocr_correction(data: OCRCorrectionCreate, db: Session = Depends(get_db)):
    """Save a correction mapping so OCR can auto-fix in the future."""
    existing = db.query(OCRCorrection).filter(
        OCRCorrection.original_text == data.original_text,
        OCRCorrection.field_type == data.field_type,
    ).first()

    if existing:
        existing.corrected_text = data.corrected_text
        existing.use_count += 1
        existing.updated_at = datetime.now()
    else:
        correction = OCRCorrection(
            original_text=data.original_text,
            corrected_text=data.corrected_text,
            field_type=data.field_type,
        )
        db.add(correction)

    db.commit()
    return {"message": "Correction saved"}

@app.get("/api/ocr/corrections")
def list_ocr_corrections(db: Session = Depends(get_db)):
    """List all OCR correction mappings."""
    corrections = db.query(OCRCorrection).order_by(OCRCorrection.use_count.desc()).all()
    return [
        {
            "id": c.id,
            "original_text": c.original_text,
            "corrected_text": c.corrected_text,
            "field_type": c.field_type,
            "use_count": c.use_count,
        }
        for c in corrections
    ]

@app.delete("/api/ocr/corrections/{correction_id}")
def delete_ocr_correction(correction_id: int, db: Session = Depends(get_db)):
    correction = db.query(OCRCorrection).filter(OCRCorrection.id == correction_id).first()
    if not correction:
        raise HTTPException(status_code=404, detail="Correction not found")
    db.delete(correction)
    db.commit()
    return {"message": "Correction deleted"}


def apply_ocr_corrections(db: Session, line_items: list) -> list:
    """Apply saved corrections to OCR output."""
    corrections = db.query(OCRCorrection).filter(
        OCRCorrection.field_type == 'product_name'
    ).all()
    correction_map = {c.original_text.lower(): c.corrected_text for c in corrections}

    for item in line_items:
        name_lower = item.get('product_name', '').lower()
        if name_lower in correction_map:
            item['product_name'] = correction_map[name_lower]
    return line_items


# ==================== DEAD STOCK DETECTION ====================

@app.get("/api/analytics/dead-stock")
def dead_stock(days_threshold: int = 45, db: Session = Depends(get_db)):
    """Products you used to buy regularly but haven't ordered recently."""
    cutoff = date.today() - timedelta(days=days_threshold)
    older_cutoff = date.today() - timedelta(days=days_threshold * 3)

    # Products with purchases in the older period but NOT in the recent period
    recent_products = db.query(func.distinct(ProductVendorPrice.product_id)).filter(
        ProductVendorPrice.invoice_date >= cutoff,
    ).subquery()

    historical = db.query(
        Product.id,
        Product.name,
        func.max(ProductVendorPrice.invoice_date).label('last_ordered'),
        func.count(ProductVendorPrice.id).label('total_purchases'),
        func.sum(ProductVendorPrice.quantity).label('total_quantity'),
    ).join(ProductVendorPrice, ProductVendorPrice.product_id == Product.id
    ).filter(
        ProductVendorPrice.invoice_date >= older_cutoff,
        ProductVendorPrice.invoice_date < cutoff,
        ~Product.id.in_(recent_products),
    ).group_by(Product.id
    ).having(func.count(ProductVendorPrice.id) >= 2  # Must have bought at least twice before
    ).order_by(desc(func.count(ProductVendorPrice.id))).all()

    return [
        {
            "id": r.id,
            "name": r.name,
            "last_ordered": r.last_ordered.isoformat() if r.last_ordered else None,
            "days_since_last_order": (date.today() - r.last_ordered).days if r.last_ordered else None,
            "total_purchases": r.total_purchases,
            "total_quantity": float(r.total_quantity) if r.total_quantity else 0,
        }
        for r in historical
    ]


# ==================== REORDER SUGGESTIONS ====================

@app.get("/api/analytics/reorder-suggestions")
def reorder_suggestions(db: Session = Depends(get_db)):
    """Suggest products that may need reordering based on purchase frequency."""
    # Get products with enough purchase history
    products = db.query(Product).filter(Product.last_ordered_date != None).all()
    suggestions = []

    for product in products:
        # Calculate average order frequency
        purchases = db.query(ProductVendorPrice.invoice_date).filter(
            ProductVendorPrice.product_id == product.id,
        ).order_by(ProductVendorPrice.invoice_date).all()

        if len(purchases) < 3:
            continue

        dates = [p.invoice_date for p in purchases]
        intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
        avg_interval = sum(intervals) / len(intervals) if intervals else 0

        if avg_interval <= 0:
            continue

        # Update stored frequency
        product.reorder_frequency_days = int(avg_interval)

        days_since = (date.today() - product.last_ordered_date).days if product.last_ordered_date else 999
        days_overdue = days_since - avg_interval

        if days_overdue > -3:  # Due within 3 days or overdue
            last_vendor = db.query(Vendor).get(product.last_vendor_id) if product.last_vendor_id else None
            suggestions.append({
                "product_id": product.id,
                "product_name": product.name,
                "avg_order_interval_days": int(avg_interval),
                "days_since_last_order": days_since,
                "days_overdue": max(0, int(days_overdue)),
                "last_vendor": last_vendor.name if last_vendor else None,
                "last_price": float(product.last_price) if product.last_price else None,
                "urgency": "overdue" if days_overdue > 3 else "due_soon" if days_overdue > -3 else "ok",
            })

    db.commit()
    suggestions.sort(key=lambda x: x['days_overdue'], reverse=True)
    return suggestions


# ==================== SEASONAL PRICE PATTERNS ====================

@app.get("/api/analytics/seasonal/{product_id}")
def seasonal_patterns(product_id: int, db: Session = Depends(get_db)):
    """Show average price by month for a product to reveal seasonal patterns."""
    rows = db.query(
        extract('month', ProductVendorPrice.invoice_date).label('month'),
        func.avg(ProductVendorPrice.unit_price).label('avg_price'),
        func.min(ProductVendorPrice.unit_price).label('min_price'),
        func.max(ProductVendorPrice.unit_price).label('max_price'),
        func.count(ProductVendorPrice.id).label('data_points'),
    ).filter(
        ProductVendorPrice.product_id == product_id,
    ).group_by(
        extract('month', ProductVendorPrice.invoice_date),
    ).order_by('month').all()

    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    return [
        {
            "month": int(r.month),
            "month_name": months[int(r.month) - 1],
            "avg_price": round(float(r.avg_price), 2),
            "min_price": float(r.min_price),
            "max_price": float(r.max_price),
            "data_points": r.data_points,
        }
        for r in rows
    ]


# ==================== INVOICE PHOTO VIEWER ====================

@app.get("/api/invoices/{invoice_id}/image")
def get_invoice_image(invoice_id: int, db: Session = Depends(get_db)):
    """Get the image path for an invoice."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not invoice.image_path:
        raise HTTPException(status_code=404, detail="No image for this invoice")
    return {"image_path": invoice.image_path}


# ==================== HELPER FUNCTIONS ====================

def _update_product_catalog(
    db: Session, item: InvoiceItemCreate, vendor_id: int,
    invoice_date: date, invoice_item_id: int = None
):
    """Update product catalog with new price data and insert into product_vendor_prices."""
    normalized = item.product_name.lower().strip()

    product = db.query(Product).filter(Product.normalized_name == normalized).first()

    if product:
        old_price = float(product.last_price) if product.last_price else None
        new_price = item.unit_price

        # Check for price change
        if old_price and abs(old_price - new_price) / old_price > 0.05:
            change_pct = ((new_price - old_price) / old_price) * 100
            alert = PriceAlert(
                product_id=product.id,
                invoice_item_id=invoice_item_id,
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
        product.last_ordered_date = invoice_date

        if not product.min_price or new_price < float(product.min_price):
            product.min_price = new_price
        if not product.max_price or new_price > float(product.max_price):
            product.max_price = new_price

        # Update price_history JSON
        history = product.price_history or []
        history.append({
            "date": invoice_date.isoformat(),
            "price": new_price,
            "vendor_id": vendor_id,
        })
        product.price_history = history

        # Recalculate avg_price
        prices = [float(h["price"]) for h in history]
        product.avg_price = sum(prices) / len(prices)

    else:
        # Auto-categorize new product
        cat_id = None
        if hasattr(item, 'category_override') and item.category_override:
            cat_id = item.category_override
        else:
            cat_id = auto_categorize_product(item.product_name, db)

        product = Product(
            name=item.product_name,
            normalized_name=normalized,
            category_id=cat_id,
            last_vendor_id=vendor_id,
            last_price=item.unit_price,
            avg_price=item.unit_price,
            min_price=item.unit_price,
            max_price=item.unit_price,
            last_ordered_date=invoice_date,
            price_history=[{
                "date": invoice_date.isoformat(),
                "price": item.unit_price,
                "vendor_id": vendor_id,
            }],
        )
        db.add(product)
        db.flush()

    # Check for price contract violations
    active_contract = db.query(PriceContract).filter(
        PriceContract.vendor_id == vendor_id,
        PriceContract.product_id == product.id,
        PriceContract.is_active == True,
        PriceContract.start_date <= invoice_date,
        PriceContract.end_date >= invoice_date,
    ).first()

    if active_contract and item.unit_price > float(active_contract.agreed_price) * 1.01:
        alert = PriceAlert(
            product_id=product.id,
            invoice_item_id=invoice_item_id,
            vendor_id=vendor_id,
            previous_price=float(active_contract.agreed_price),
            new_price=item.unit_price,
            change_percent=((item.unit_price - float(active_contract.agreed_price)) / float(active_contract.agreed_price)) * 100,
            alert_type='increase'
        )
        db.add(alert)

    # If category_override provided, update existing product category too
    if hasattr(item, 'category_override') and item.category_override and product.category_id is None:
        product.category_id = item.category_override

    # Insert into product_vendor_prices
    pvp = ProductVendorPrice(
        product_id=product.id,
        vendor_id=vendor_id,
        invoice_item_id=invoice_item_id,
        invoice_date=invoice_date,
        unit_price=item.unit_price,
        quantity=item.quantity,
        unit=item.unit,
    )
    db.add(pvp)


# ==================== DELI MODULE ====================

class DeliItemCreate(BaseModel):
    product_name: str
    product_id: Optional[int] = None
    current_quantity: float = 0
    par_level: float = 0
    unit: str = 'ea'

class DeliItemUpdate(BaseModel):
    current_quantity: Optional[float] = None
    par_level: Optional[float] = None

class DeliveryScheduleCreate(BaseModel):
    vendor_id: int
    delivery_days: str  # "mon,wed,fri"
    cutoff_time: Optional[str] = None
    lead_days: int = 1
    notes: Optional[str] = None

@app.get("/api/deli/inventory")
def list_deli_inventory(db: Session = Depends(get_db)):
    """List deli inventory items with par level status."""
    items = db.query(DeliInventory).order_by(DeliInventory.product_name).all()
    return [item.to_dict() for item in items]

@app.post("/api/deli/inventory")
def add_deli_item(data: DeliItemCreate, db: Session = Depends(get_db)):
    item = DeliInventory(
        product_id=data.product_id,
        product_name=data.product_name,
        current_quantity=data.current_quantity,
        par_level=data.par_level,
        unit=data.unit,
        last_counted_at=datetime.now(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item.to_dict()

@app.put("/api/deli/inventory/{item_id}")
def update_deli_item(item_id: int, data: DeliItemUpdate, db: Session = Depends(get_db)):
    item = db.query(DeliInventory).filter(DeliInventory.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Deli item not found")
    if data.current_quantity is not None:
        item.current_quantity = data.current_quantity
        item.last_counted_at = datetime.now()
    if data.par_level is not None:
        item.par_level = data.par_level
    db.commit()
    db.refresh(item)
    return item.to_dict()

@app.delete("/api/deli/inventory/{item_id}")
def delete_deli_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(DeliInventory).filter(DeliInventory.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Deli item not found")
    db.delete(item)
    db.commit()
    return {"message": "Item deleted"}

@app.get("/api/deli/vendors")
def list_deli_vendors(db: Session = Depends(get_db)):
    """List vendors flagged as deli vendors."""
    vendors = db.query(Vendor).filter(Vendor.is_deli_vendor == True, Vendor.is_active == True).all()
    return [v.to_dict() for v in vendors]

@app.put("/api/vendors/{vendor_id}/deli-flag")
def toggle_deli_vendor(vendor_id: int, is_deli: bool = True, db: Session = Depends(get_db)):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    vendor.is_deli_vendor = is_deli
    db.commit()
    return {"message": f"Vendor {'flagged' if is_deli else 'unflagged'} as deli vendor"}

@app.get("/api/deli/order-sheet/{vendor_id}")
def generate_order_sheet(vendor_id: int, db: Session = Depends(get_db)):
    """Generate order sheet from par level deficits."""
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    items = db.query(DeliInventory).all()
    order_items = []
    for item in items:
        deficit = max(0, float(item.par_level or 0) - float(item.current_quantity or 0))
        if deficit > 0:
            order_items.append({
                "product_name": item.product_name,
                "order_qty": deficit,
                "unit": item.unit,
                "par_level": float(item.par_level or 0),
                "current_qty": float(item.current_quantity or 0),
            })

    return {
        "vendor_id": vendor_id,
        "vendor_name": vendor.name,
        "items": order_items,
        "total_items": len(order_items),
    }

@app.get("/api/deli/delivery-schedule")
def list_delivery_schedules(db: Session = Depends(get_db)):
    """List delivery schedules for deli vendors."""
    schedules = db.query(VendorDeliverySchedule).all()
    return [s.to_dict() for s in schedules]

@app.post("/api/deli/delivery-schedule")
def create_delivery_schedule(data: DeliveryScheduleCreate, db: Session = Depends(get_db)):
    schedule = VendorDeliverySchedule(
        vendor_id=data.vendor_id,
        delivery_days=data.delivery_days,
        cutoff_time=data.cutoff_time,
        lead_days=data.lead_days,
        notes=data.notes,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule.to_dict()

@app.post("/api/admin/migrate")
def run_migration(db: Session = Depends(get_db)):
    """Add new columns to existing tables (for upgrades)."""
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        vendor_cols = [c['name'] for c in inspector.get_columns('vendors')]
        if 'is_deli_vendor' not in vendor_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE vendors ADD COLUMN is_deli_vendor BOOLEAN DEFAULT FALSE"))
                conn.commit()
        return {"message": "Migration complete"}
    except Exception as e:
        return {"message": f"Migration note: {e}"}


# ==================== DATABASE BACKUP ====================

@app.post("/api/admin/backup")
def manual_backup():
    """Create a manual database backup."""
    if "sqlite" not in DATABASE_URL:
        return {"message": "Backup only available for SQLite"}
    db_path = Path("./purchase_tracker.db")
    if not db_path.exists() or db_path.stat().st_size == 0:
        raise HTTPException(status_code=400, detail="No database to back up")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"purchase_tracker_{timestamp}.db"
    shutil.copy2(str(db_path), str(backup_path))
    backups = sorted(BACKUP_DIR.glob("purchase_tracker_*.db"))
    return {
        "message": f"Backup created: {backup_path.name}",
        "backup_count": len(backups),
    }

@app.get("/api/admin/backups")
def list_backups():
    """List available database backups."""
    backups = sorted(BACKUP_DIR.glob("purchase_tracker_*.db"), reverse=True)
    return [
        {"name": b.name, "size": b.stat().st_size, "date": datetime.fromtimestamp(b.stat().st_mtime).isoformat()}
        for b in backups
    ]


# ==================== SEED DATA ====================

@app.post("/api/seed")
def seed_database(db: Session = Depends(get_db)):
    if db.query(Category).count() > 0:
        return {"message": "Database already seeded"}

    categories = [
        Category(name="Grocery/Dry Goods", description="Krasdale, shelf-stable items", target_budget_percent=35),
        Category(name="Deli/Specialty", description="Deli items, specialty snacks, wellness", target_budget_percent=10),
        Category(name="Dairy", description="Milk, eggs, cheese, yogurt", target_budget_percent=12),
        Category(name="Frozen", description="Frozen foods, ice cream", target_budget_percent=8),
        Category(name="Beverages", description="Sodas, juices, water", target_budget_percent=10),
        Category(name="Produce", description="Fresh fruits and vegetables", target_budget_percent=15),
        Category(name="Meat/Seafood", description="Fresh and packaged meats", target_budget_percent=8),
        Category(name="Bakery", description="Bread, pastries", target_budget_percent=2),
        Category(name="Snacks/Chips", description="Chips, pretzels, crackers, snack foods", target_budget_percent=5),
        Category(name="Candy/Chocolate", description="Candy bars, chocolate, sweets, gummies", target_budget_percent=5),
        Category(name="Paper Goods", description="Paper towels, napkins, plates, cups", target_budget_percent=3),
        Category(name="Cleaning", description="Cleaning supplies, trash bags, detergent", target_budget_percent=2),
    ]

    for cat in categories:
        db.add(cat)
    db.commit()

    deli_cat = db.query(Category).filter(Category.name == "Deli/Specialty").first()

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
    db = SessionLocal()
    try:
        if db.query(Category).count() == 0:
            seed_database(db)
    finally:
        db.close()


# ==================== FRONTEND ROUTES ====================

@app.get("/manifest.json")
async def serve_manifest():
    manifest_path = FRONTEND_DIR / "manifest.json"
    if manifest_path.exists():
        return FileResponse(str(manifest_path), media_type="application/json")
    raise HTTPException(status_code=404)

@app.get("/")
async def serve_index():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Apple Tree Purchase Tracker API v2.1"}

@app.get("/{path:path}")
async def catch_all(path: str):
    """SPA catch-all: serve index.html for non-API, non-static routes."""
    if path.startswith("api/") or path.startswith("uploads/") or path.startswith("static/"):
        raise HTTPException(status_code=404)
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    raise HTTPException(status_code=404)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
