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
    default_due_days INTEGER DEFAULT 30, -- Days until payment due
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
    has_shortage BOOLEAN DEFAULT FALSE,
    shortage_total DECIMAL(12,2) DEFAULT 0,
    dispute_reason TEXT,
    dispute_status VARCHAR(50), -- open, resolved, credited
    credit_amount DECIMAL(12,2),
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
    received_quantity DECIMAL(10,3), -- Actually received (for shortage tracking)
    unit VARCHAR(50), -- case, each, lb, etc.
    unit_price DECIMAL(10,2) NOT NULL,
    total_price DECIMAL(12,2) NOT NULL,
    category_override INTEGER REFERENCES categories(id), -- If different from vendor category
    is_disputed BOOLEAN DEFAULT FALSE,
    dispute_reason TEXT,
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
    sell_price DECIMAL(10,2), -- Retail shelf price
    units_per_case INTEGER, -- How many units in a case
    target_margin DECIMAL(5,2), -- Target profit margin %
    price_history JSONB, -- Array of {date, price, vendor_id}
    reorder_frequency_days INTEGER, -- Avg days between orders
    last_ordered_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Product vendor prices (one row per invoice line item for analytics)
CREATE TABLE product_vendor_prices (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id) NOT NULL,
    vendor_id INTEGER REFERENCES vendors(id) NOT NULL,
    invoice_item_id INTEGER REFERENCES invoice_items(id),
    invoice_date DATE NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    quantity DECIMAL(10,3),
    unit VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

-- Competitor stores for regional price comparison
CREATE TABLE competitor_stores (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    website_url TEXT,
    scraper_type VARCHAR(50) DEFAULT 'manual',
    scraper_config JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    last_scraped_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Competitor prices
CREATE TABLE competitor_prices (
    id SERIAL PRIMARY KEY,
    store_id INTEGER REFERENCES competitor_stores(id) NOT NULL,
    product_name VARCHAR(500) NOT NULL,
    normalized_name VARCHAR(500),
    matched_product_id INTEGER REFERENCES products(id),
    price DECIMAL(10,2) NOT NULL,
    unit VARCHAR(50),
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Recommendations (deal detection & smart insights)
CREATE TABLE recommendations (
    id SERIAL PRIMARY KEY,
    type VARCHAR(50) NOT NULL,
    product_id INTEGER REFERENCES products(id),
    vendor_id INTEGER REFERENCES vendors(id),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    potential_savings DECIMAL(10,2),
    priority INTEGER DEFAULT 5,
    is_dismissed BOOLEAN DEFAULT FALSE,
    is_acted_on BOOLEAN DEFAULT FALSE,
    data JSONB,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- OCR correction mappings (learns from user corrections)
CREATE TABLE ocr_corrections (
    id SERIAL PRIMARY KEY,
    original_text VARCHAR(500) NOT NULL,
    corrected_text VARCHAR(500) NOT NULL,
    field_type VARCHAR(50) DEFAULT 'product_name', -- product_name, vendor_name
    use_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Price contracts (agreed prices with vendors)
CREATE TABLE price_contracts (
    id SERIAL PRIMARY KEY,
    vendor_id INTEGER REFERENCES vendors(id) NOT NULL,
    product_id INTEGER REFERENCES products(id) NOT NULL,
    agreed_price DECIMAL(10,2) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE,
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
CREATE INDEX idx_pvp_product_date ON product_vendor_prices(product_id, invoice_date);
CREATE INDEX idx_pvp_vendor_product ON product_vendor_prices(vendor_id, product_id);
CREATE INDEX idx_cp_store_product ON competitor_prices(store_id, normalized_name);
CREATE INDEX idx_ocr_original ON ocr_corrections(original_text);
CREATE INDEX idx_contract_vendor_product ON price_contracts(vendor_id, product_id);

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
