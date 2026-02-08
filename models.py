"""
Apple Tree Purchase Tracker - Database Models
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Text, Numeric, Boolean,
    Date, DateTime, ForeignKey, UniqueConstraint, JSON, Index, Float
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Category(Base):
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    target_budget_percent = Column(Numeric(5, 2))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    vendors = relationship("Vendor", back_populates="category")
    products = relationship("Product", back_populates="category")
    monthly_budgets = relationship("MonthlyBudget", back_populates="category")


class Vendor(Base):
    __tablename__ = 'vendors'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'))
    address = Column(Text)
    phone = Column(String(50))
    email = Column(String(255))
    contact_person = Column(String(255))
    payment_terms = Column(String(100))  # NET30, COD, etc.
    default_due_days = Column(Integer, default=30)  # Days until payment due
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    category = relationship("Category", back_populates="vendors")
    invoices = relationship("Invoice", back_populates="vendor")

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else None,
            'address': self.address,
            'phone': self.phone,
            'email': self.email,
            'contact_person': self.contact_person,
            'payment_terms': self.payment_terms,
            'default_due_days': self.default_due_days,
            'is_active': self.is_active
        }


class Invoice(Base):
    __tablename__ = 'invoices'
    __table_args__ = (
        UniqueConstraint('vendor_id', 'invoice_number', name='uq_vendor_invoice'),
    )

    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'))
    invoice_number = Column(String(100))
    invoice_date = Column(Date, nullable=False)
    received_date = Column(Date)
    due_date = Column(Date)
    subtotal = Column(Numeric(12, 2))
    tax = Column(Numeric(12, 2), default=0)
    total = Column(Numeric(12, 2), nullable=False)
    status = Column(String(50), default='pending')  # pending, verified, paid, disputed
    payment_date = Column(Date)
    payment_method = Column(String(50))
    payment_reference = Column(String(255))
    image_path = Column(Text)
    ocr_raw_text = Column(Text)
    has_shortage = Column(Boolean, default=False)
    shortage_total = Column(Numeric(12, 2), default=0)
    dispute_reason = Column(Text)
    dispute_status = Column(String(50))  # open, resolved, credited
    credit_amount = Column(Numeric(12, 2))
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    vendor = relationship("Vendor", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")

    def to_dict(self, include_items=False):
        result = {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.name if self.vendor else None,
            'category_name': self.vendor.category.name if self.vendor and self.vendor.category else None,
            'invoice_number': self.invoice_number,
            'invoice_date': self.invoice_date.isoformat() if self.invoice_date else None,
            'received_date': self.received_date.isoformat() if self.received_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'total': float(self.total) if self.total else 0,
            'status': self.status,
            'item_count': len(self.items) if self.items else 0,
            'has_shortage': self.has_shortage or False,
            'shortage_total': float(self.shortage_total) if self.shortage_total else 0,
            'dispute_status': self.dispute_status,
            'image_path': self.image_path,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_items:
            result['items'] = [item.to_dict() for item in self.items]
        return result


class InvoiceItem(Base):
    __tablename__ = 'invoice_items'

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey('invoices.id', ondelete='CASCADE'))
    product_name = Column(String(500), nullable=False)
    product_code = Column(String(100))
    quantity = Column(Numeric(10, 3), nullable=False)  # Ordered quantity
    received_quantity = Column(Numeric(10, 3))  # Actually received
    unit = Column(String(50))
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_price = Column(Numeric(12, 2), nullable=False)
    category_override = Column(Integer, ForeignKey('categories.id'))
    is_disputed = Column(Boolean, default=False)
    dispute_reason = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())

    invoice = relationship("Invoice", back_populates="items")

    def to_dict(self):
        shortage = 0
        if self.received_quantity is not None and self.quantity:
            shortage = float(self.quantity) - float(self.received_quantity)
        return {
            'id': self.id,
            'product_name': self.product_name,
            'product_code': self.product_code,
            'quantity': float(self.quantity) if self.quantity else 0,
            'received_quantity': float(self.received_quantity) if self.received_quantity is not None else None,
            'shortage': max(0, shortage),
            'unit': self.unit,
            'unit_price': float(self.unit_price) if self.unit_price else 0,
            'total_price': float(self.total_price) if self.total_price else 0,
            'is_disputed': self.is_disputed or False,
            'dispute_reason': self.dispute_reason,
        }


class Product(Base):
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True)
    name = Column(String(500), nullable=False)
    normalized_name = Column(String(500))
    upc = Column(String(50))
    category_id = Column(Integer, ForeignKey('categories.id'))
    last_vendor_id = Column(Integer, ForeignKey('vendors.id'))
    last_price = Column(Numeric(10, 2))
    avg_price = Column(Numeric(10, 2))
    min_price = Column(Numeric(10, 2))
    max_price = Column(Numeric(10, 2))
    sell_price = Column(Numeric(10, 2))  # Retail shelf price
    units_per_case = Column(Integer)  # How many units in a case
    target_margin = Column(Numeric(5, 2))  # Target profit margin %
    price_history = Column(JSON)
    reorder_frequency_days = Column(Integer)  # Avg days between orders
    last_ordered_date = Column(Date)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    category = relationship("Category", back_populates="products")

    __table_args__ = (
        Index('idx_products_normalized', normalized_name),
    )


class ProductVendorPrice(Base):
    """One row per invoice line item - tracks price per product per vendor over time."""
    __tablename__ = 'product_vendor_prices'

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False)
    invoice_item_id = Column(Integer, ForeignKey('invoice_items.id'))
    invoice_date = Column(Date, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    quantity = Column(Numeric(10, 3))
    unit = Column(String(50))
    created_at = Column(DateTime, default=func.now())

    product = relationship("Product")
    vendor = relationship("Vendor")

    __table_args__ = (
        Index('idx_pvp_product_date', product_id, invoice_date),
        Index('idx_pvp_vendor_product', vendor_id, product_id),
    )


class DailySales(Base):
    __tablename__ = 'daily_sales'

    id = Column(Integer, primary_key=True)
    sale_date = Column(Date, nullable=False, unique=True)
    gross_sales = Column(Numeric(12, 2), nullable=False)
    net_sales = Column(Numeric(12, 2))
    transaction_count = Column(Integer)
    notes = Column(Text)
    source = Column(String(50), default='manual')
    created_at = Column(DateTime, default=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'sale_date': self.sale_date.isoformat(),
            'gross_sales': float(self.gross_sales) if self.gross_sales else 0,
            'net_sales': float(self.net_sales) if self.net_sales else 0,
            'transaction_count': self.transaction_count,
            'source': self.source
        }


class MonthlyBudget(Base):
    __tablename__ = 'monthly_budgets'
    __table_args__ = (
        UniqueConstraint('year_month', 'category_id', name='uq_month_category'),
    )

    id = Column(Integer, primary_key=True)
    year_month = Column(Date, nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'))
    target_amount = Column(Numeric(12, 2))
    target_percent = Column(Numeric(5, 2))
    actual_amount = Column(Numeric(12, 2), default=0)
    variance = Column(Numeric(12, 2), default=0)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    category = relationship("Category", back_populates="monthly_budgets")


class PriceAlert(Base):
    __tablename__ = 'price_alerts'

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'))
    invoice_item_id = Column(Integer, ForeignKey('invoice_items.id'))
    vendor_id = Column(Integer, ForeignKey('vendors.id'))
    previous_price = Column(Numeric(10, 2))
    new_price = Column(Numeric(10, 2))
    change_percent = Column(Numeric(5, 2))
    alert_type = Column(String(50))
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String(255))
    acknowledged_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())


class AuditLog(Base):
    __tablename__ = 'audit_log'

    id = Column(Integer, primary_key=True)
    table_name = Column(String(100))
    record_id = Column(Integer)
    action = Column(String(50))
    old_values = Column(JSON)
    new_values = Column(JSON)
    user_id = Column(String(255))
    created_at = Column(DateTime, default=func.now())


# ==================== Competitor Stores ====================

class CompetitorStore(Base):
    __tablename__ = 'competitor_stores'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    website_url = Column(Text)
    scraper_type = Column(String(50), default='manual')
    scraper_config = Column(JSON)
    is_active = Column(Boolean, default=True)
    last_scraped_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class CompetitorPrice(Base):
    __tablename__ = 'competitor_prices'

    id = Column(Integer, primary_key=True)
    store_id = Column(Integer, ForeignKey('competitor_stores.id'), nullable=False)
    product_name = Column(String(500), nullable=False)
    normalized_name = Column(String(500))
    matched_product_id = Column(Integer, ForeignKey('products.id'))
    price = Column(Numeric(10, 2), nullable=False)
    unit = Column(String(50))
    scraped_at = Column(DateTime, default=func.now())
    is_current = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

    store = relationship("CompetitorStore")
    matched_product = relationship("Product")

    __table_args__ = (
        Index('idx_cp_store_product', store_id, normalized_name),
    )


# ==================== Recommendations ====================

class Recommendation(Base):
    __tablename__ = 'recommendations'

    id = Column(Integer, primary_key=True)
    type = Column(String(50), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'))
    vendor_id = Column(Integer, ForeignKey('vendors.id'))
    title = Column(String(500), nullable=False)
    description = Column(Text)
    potential_savings = Column(Numeric(10, 2))
    priority = Column(Integer, default=5)
    is_dismissed = Column(Boolean, default=False)
    is_acted_on = Column(Boolean, default=False)
    data = Column(JSON)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    product = relationship("Product")
    vendor = relationship("Vendor")


# ==================== OCR Correction Mappings ====================

class OCRCorrection(Base):
    """Learns from user corrections to auto-fix OCR output."""
    __tablename__ = 'ocr_corrections'

    id = Column(Integer, primary_key=True)
    original_text = Column(String(500), nullable=False)
    corrected_text = Column(String(500), nullable=False)
    field_type = Column(String(50), default='product_name')  # product_name, vendor_name
    use_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_ocr_original', original_text),
    )


# ==================== Price Contracts ====================

class PriceContract(Base):
    """Tracks agreed prices with vendors for specific products."""
    __tablename__ = 'price_contracts'

    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    agreed_price = Column(Numeric(10, 2), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

    vendor = relationship("Vendor")
    product = relationship("Product")

    __table_args__ = (
        Index('idx_contract_vendor_product', vendor_id, product_id),
    )
