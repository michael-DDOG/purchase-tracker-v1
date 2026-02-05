-- Apple Tree Purchase Tracking System
-- Database Schema

-- Categories for organizing vendors and tracking budgets
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    target_budget_percent DECIMAL(5,2), -- Target % of monthly sales
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vendors/Suppliers
CREATE TABLE vendors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    address TEXT,
    phone VARCHAR(50),
    email VARCHAR(255),
    contact_person VARCHAR(255),
    payment_terms VARCHAR(100), -- NET30, COD, etc.
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Invoices (header information)
CREATE TABLE invoices (
    id SERIAL PRIMARY KEY,
    vendor_id INTEGER REFERENCES vendors(id),
    invoice_number VARCHAR(100),
    invoice_date DATE NOT NULL,
    received_date DATE, -- When you actually received the goods
    due_date DATE,
    subtotal DECIMAL(12,2),
    tax DECIMAL(12,2) DEFAULT 0,
    total DECIMAL(12,2) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending', -- pending, verified, paid, disputed
    payment_date DATE,
    payment_method VARCHAR(50),
    payment_reference VARCHAR(255),
    image_path TEXT, -- Path to stored invoice image
    ocr_raw_text TEXT, -- Raw OCR output for debugging
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Composite unique constraint to prevent duplicates
    UNIQUE(vendor_id, invoice_number)
);

-- Invoice line items
CREATE TABLE invoice_items (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER REFERENCES invoices(id) ON DELETE CASCADE,
    product_name VARCHAR(500) NOT NULL,
    product_code VARCHAR(100), -- UPC, SKU, etc.
    quantity DECIMAL(10,3) NOT NULL,
    unit VARCHAR(50), -- case, each, lb, etc.
    unit_price DECIMAL(10,2) NOT NULL,
    total_price DECIMAL(12,2) NOT NULL,
    category_override INTEGER REFERENCES categories(id), -- If different from vendor category
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Product catalog (for tracking price history and auto-categorization)
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    normalized_name VARCHAR(500), -- Lowercase, trimmed for matching
    upc VARCHAR(50),
    category_id INTEGER REFERENCES categories(id),
    last_vendor_id INTEGER REFERENCES vendors(id),
    last_price DECIMAL(10,2),
    avg_price DECIMAL(10,2),
    min_price DECIMAL(10,2),
    max_price DECIMAL(10,2),
    price_history JSONB, -- Array of {date, price, vendor_id}
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily sales figures (manual entry or ECRS import)
CREATE TABLE daily_sales (
    id SERIAL PRIMARY KEY,
    sale_date DATE NOT NULL UNIQUE,
    gross_sales DECIMAL(12,2) NOT NULL,
    net_sales DECIMAL(12,2),
    transaction_count INTEGER,
    notes TEXT,
    source VARCHAR(50) DEFAULT 'manual', -- manual, ecrs_import
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Monthly budgets and targets
CREATE TABLE monthly_budgets (
    id SERIAL PRIMARY KEY,
    year_month DATE NOT NULL, -- First day of month
    category_id INTEGER REFERENCES categories(id),
    target_amount DECIMAL(12,2),
    target_percent DECIMAL(5,2),
    actual_amount DECIMAL(12,2) DEFAULT 0,
    variance DECIMAL(12,2) DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(year_month, category_id)
);

-- Price alerts (when prices change significantly)
CREATE TABLE price_alerts (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    invoice_item_id INTEGER REFERENCES invoice_items(id),
    vendor_id INTEGER REFERENCES vendors(id),
    previous_price DECIMAL(10,2),
    new_price DECIMAL(10,2),
    change_percent DECIMAL(5,2),
    alert_type VARCHAR(50), -- increase, decrease, new_product
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(255),
    acknowledged_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit log for tracking changes
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(100),
    record_id INTEGER,
    action VARCHAR(50), -- insert, update, delete
    old_values JSONB,
    new_values JSONB,
    user_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default categories
INSERT INTO categories (name, description, target_budget_percent) VALUES
    ('Grocery/Dry Goods', 'Krasdale, shelf-stable items, bulk grocery', 35.00),
    ('Deli/Specialty', 'Deli items, specialty snacks, wellness products', 10.00),
    ('Dairy', 'Milk, eggs, cheese, yogurt', 12.00),
    ('Frozen', 'Frozen foods, ice cream, frozen meals', 8.00),
    ('Beverages', 'Sodas, juices, water, energy drinks', 10.00),
    ('Produce', 'Fresh fruits and vegetables', 15.00),
    ('Meat/Seafood', 'Fresh and packaged meats, seafood', 8.00),
    ('Bakery', 'Bread, pastries, baked goods', 2.00);

-- Create indexes for common queries
CREATE INDEX idx_invoices_vendor ON invoices(vendor_id);
CREATE INDEX idx_invoices_date ON invoices(invoice_date);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoice_items_invoice ON invoice_items(invoice_id);
CREATE INDEX idx_products_normalized ON products(normalized_name);
CREATE INDEX idx_daily_sales_date ON daily_sales(sale_date);
CREATE INDEX idx_price_alerts_unack ON price_alerts(is_acknowledged) WHERE NOT is_acknowledged;

-- Create view for invoice summary with vendor info
CREATE VIEW invoice_summary AS
SELECT 
    i.id,
    i.invoice_number,
    i.invoice_date,
    i.total,
    i.status,
    v.name as vendor_name,
    c.name as category_name,
    COUNT(ii.id) as item_count
FROM invoices i
JOIN vendors v ON i.vendor_id = v.id
LEFT JOIN categories c ON v.category_id = c.id
LEFT JOIN invoice_items ii ON i.id = ii.invoice_id
GROUP BY i.id, v.name, c.name;

-- Create view for daily purchase totals by category
CREATE VIEW daily_purchases_by_category AS
SELECT 
    i.invoice_date,
    c.id as category_id,
    c.name as category_name,
    SUM(i.total) as total_purchases,
    COUNT(DISTINCT i.id) as invoice_count
FROM invoices i
JOIN vendors v ON i.vendor_id = v.id
JOIN categories c ON v.category_id = c.id
GROUP BY i.invoice_date, c.id, c.name;

-- Create view for monthly spending summary
CREATE VIEW monthly_spending_summary AS
SELECT 
    DATE_TRUNC('month', i.invoice_date) as month,
    c.id as category_id,
    c.name as category_name,
    c.target_budget_percent,
    SUM(i.total) as total_spent,
    COUNT(DISTINCT i.id) as invoice_count,
    COUNT(DISTINCT i.vendor_id) as vendor_count
FROM invoices i
JOIN vendors v ON i.vendor_id = v.id
JOIN categories c ON v.category_id = c.id
GROUP BY DATE_TRUNC('month', i.invoice_date), c.id, c.name, c.target_budget_percent;
