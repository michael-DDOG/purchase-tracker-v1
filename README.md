# 🛒 Apple Tree Purchase Tracker

A comprehensive purchase tracking system for supermarket operations. Track vendor invoices, manage purchasing budgets by category, and analyze spending patterns.

## Features

- 📸 **Invoice OCR** - Take photos of invoices and automatically extract data
- 📊 **Dashboard** - Real-time spending overview with budget tracking
- 🏷️ **Category Management** - Organize spending by: Grocery, Deli, Dairy, Frozen, Beverages, Produce, Meat, Bakery
- 📈 **Budget Tracking** - Set target percentages for each category based on sales
- 🔔 **Price Alerts** - Get notified when product prices change significantly
- 📱 **Mobile-First** - Designed for use on the floor while receiving deliveries

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone and start
cd purchase-tracker
docker-compose up -d

# Access
# - Frontend: http://localhost:3000
# - API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
```

### Option 2: Local Development

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm start
```

## System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Mobile/Web    │────▶│   FastAPI       │────▶│   PostgreSQL    │
│   React App     │◀────│   Backend       │◀────│   Database      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │   Tesseract     │
                        │   OCR Engine    │
                        └─────────────────┘
```

## API Endpoints

### Dashboard
- `GET /api/dashboard/summary` - Get overview stats
- `GET /api/dashboard/budget-status` - Budget vs actual by category
- `GET /api/dashboard/spending-trend` - Daily spending over time

### Invoices
- `GET /api/invoices` - List invoices (with filters)
- `POST /api/invoices` - Create invoice with line items
- `GET /api/invoices/{id}` - Get invoice details
- `PUT /api/invoices/{id}/status` - Update status (pending/verified/paid)
- `DELETE /api/invoices/{id}` - Delete invoice

### Vendors
- `GET /api/vendors` - List vendors
- `POST /api/vendors` - Create vendor
- `GET /api/vendors/{id}` - Get vendor with stats
- `PUT /api/vendors/{id}` - Update vendor

### OCR
- `POST /api/ocr/process` - Upload invoice image for extraction

### Sales
- `GET /api/sales` - List daily sales
- `POST /api/sales` - Record daily sales

### Categories
- `GET /api/categories` - List categories
- `POST /api/categories` - Create category

## Database Schema

### Core Tables
- **categories** - Spending categories with budget targets
- **vendors** - Supplier information
- **invoices** - Invoice headers
- **invoice_items** - Line items for each invoice
- **products** - Product catalog with price history
- **daily_sales** - Sales figures (manual or ECRS import)
- **price_alerts** - Notifications for price changes

## Category Budget Targets

Default targets (% of monthly sales):

| Category | Target % |
|----------|----------|
| Grocery/Dry Goods | 35% |
| Produce | 15% |
| Dairy | 12% |
| Deli/Specialty | 10% |
| Beverages | 10% |
| Frozen | 8% |
| Meat/Seafood | 8% |
| Bakery | 2% |

## Workflow

1. **Receive Delivery** - Vendor arrives with goods
2. **Snap Invoice** - Take photo with phone
3. **Review & Confirm** - OCR extracts data, you verify
4. **Save** - Invoice is stored and budget updated
5. **Track** - Dashboard shows spending vs budget

## ECRS Integration (Future)

The system is designed to eventually integrate with ECRS Catapult:
- Import daily sales from Web Office reports
- Sync product catalog
- Potential API integration via Passport API

## Deployment Options

### Railway (Recommended)
```bash
# Install Railway CLI
npm install -g @railway/cli

# Deploy
railway login
railway init
railway up
```

### AWS / DigitalOcean
Use the provided Docker Compose with managed PostgreSQL.

### Self-Hosted
Run Docker Compose on any Linux server with Docker installed.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| DATABASE_URL | PostgreSQL connection string | sqlite:///./purchase_tracker.db |
| UPLOAD_DIR | Directory for invoice images | ./uploads |

## Mobile Usage Tips

1. **Good lighting** - Better OCR results
2. **Flat surface** - Reduce skew
3. **Full invoice** - Capture all edges
4. **Review totals** - Always verify the extracted total matches

## Contributing

Built for Apple Tree Market. Fork and customize for your own retail operation!

## License

MIT License - Use freely for your business.
