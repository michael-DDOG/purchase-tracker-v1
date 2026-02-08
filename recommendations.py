"""
Apple Tree Purchase Tracker - Recommendation Engine
Analyzes price data, vendor behavior, and competitor prices to generate actionable recommendations.
"""

from datetime import datetime, date, timedelta
from typing import List
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from models import (
    Product, ProductVendorPrice, Vendor, CompetitorPrice,
    CompetitorStore, Recommendation, InvoiceItem, Invoice
)


class RecommendationEngine:
    """Generates smart recommendations based on price and volume data."""

    def __init__(self, db: Session):
        self.db = db

    def generate_all(self) -> int:
        """Run all checks and return the number of new recommendations created."""
        # Clear expired, non-dismissed recommendations
        self.db.query(Recommendation).filter(
            Recommendation.is_dismissed == False,
            Recommendation.is_acted_on == False,
            Recommendation.expires_at != None,
            Recommendation.expires_at < datetime.now(),
        ).delete()

        count = 0
        count += self._check_cheaper_existing_vendors()
        count += self._check_price_increase_patterns()
        count += self._check_regional_prices()
        count += self._check_volume_anomalies()

        self.db.commit()
        return count

    def _recommendation_exists(self, rec_type: str, product_id: int = None, vendor_id: int = None) -> bool:
        """Check if an active recommendation of this type already exists."""
        q = self.db.query(Recommendation).filter(
            Recommendation.type == rec_type,
            Recommendation.is_dismissed == False,
            Recommendation.is_acted_on == False,
        )
        if product_id:
            q = q.filter(Recommendation.product_id == product_id)
        if vendor_id:
            q = q.filter(Recommendation.vendor_id == vendor_id)
        return q.first() is not None

    def _check_cheaper_existing_vendors(self) -> int:
        """Find products that are cheaper from a different vendor you already buy from."""
        count = 0
        cutoff = date.today() - timedelta(days=90)

        # Get recent prices per product per vendor
        recent_prices = self.db.query(
            ProductVendorPrice.product_id,
            ProductVendorPrice.vendor_id,
            func.avg(ProductVendorPrice.unit_price).label('avg_price'),
        ).filter(
            ProductVendorPrice.invoice_date >= cutoff
        ).group_by(
            ProductVendorPrice.product_id,
            ProductVendorPrice.vendor_id,
        ).all()

        # Group by product
        product_vendors = {}
        for pid, vid, avg_price in recent_prices:
            if pid not in product_vendors:
                product_vendors[pid] = []
            product_vendors[pid].append((vid, float(avg_price)))

        for pid, vendor_prices in product_vendors.items():
            if len(vendor_prices) < 2:
                continue

            vendor_prices.sort(key=lambda x: x[1])
            cheapest_vid, cheapest_price = vendor_prices[0]

            for vid, price in vendor_prices[1:]:
                savings_pct = ((price - cheapest_price) / price) * 100
                if savings_pct < 5:
                    continue

                if self._recommendation_exists('cheaper_vendor', product_id=pid, vendor_id=vid):
                    continue

                product = self.db.query(Product).get(pid)
                cheap_vendor = self.db.query(Vendor).get(cheapest_vid)
                expensive_vendor = self.db.query(Vendor).get(vid)

                if not all([product, cheap_vendor, expensive_vendor]):
                    continue

                monthly_savings = (price - cheapest_price) * 4  # Rough estimate

                rec = Recommendation(
                    type='cheaper_vendor',
                    product_id=pid,
                    vendor_id=vid,
                    title=f"Switch {product.name} to {cheap_vendor.name}",
                    description=f"You pay ${price:.2f} from {expensive_vendor.name} but {cheap_vendor.name} sells it for ${cheapest_price:.2f} ({savings_pct:.0f}% less).",
                    potential_savings=monthly_savings,
                    priority=3,
                    data={'cheapest_vendor_id': cheapest_vid, 'cheapest_price': cheapest_price, 'current_price': price},
                    expires_at=datetime.now() + timedelta(days=30),
                )
                self.db.add(rec)
                count += 1

        return count

    def _check_price_increase_patterns(self) -> int:
        """Flag vendors who have raised prices on 3+ items recently."""
        count = 0
        cutoff = date.today() - timedelta(days=60)

        vendors = self.db.query(Vendor).filter(Vendor.is_active == True).all()

        for vendor in vendors:
            # Get products with price increases from this vendor
            increases = self.db.query(
                ProductVendorPrice.product_id,
                func.min(ProductVendorPrice.unit_price).label('min_price'),
                func.max(ProductVendorPrice.unit_price).label('max_price'),
            ).filter(
                ProductVendorPrice.vendor_id == vendor.id,
                ProductVendorPrice.invoice_date >= cutoff,
            ).group_by(
                ProductVendorPrice.product_id,
            ).having(
                func.max(ProductVendorPrice.unit_price) > func.min(ProductVendorPrice.unit_price) * 1.05
            ).all()

            if len(increases) < 3:
                continue

            if self._recommendation_exists('price_increase', vendor_id=vendor.id):
                continue

            total_increase = sum(float(mx) - float(mn) for _, mn, mx in increases)

            rec = Recommendation(
                type='price_increase',
                vendor_id=vendor.id,
                title=f"{vendor.name} raised prices on {len(increases)} items",
                description=f"In the last 60 days, {vendor.name} has increased prices on {len(increases)} products. Consider negotiating or finding alternatives.",
                potential_savings=total_increase,
                priority=2,
                data={'affected_product_count': len(increases)},
                expires_at=datetime.now() + timedelta(days=14),
            )
            self.db.add(rec)
            count += 1

        return count

    def _check_regional_prices(self) -> int:
        """Find products where a competitor store has a lower price."""
        count = 0

        competitor_prices = self.db.query(CompetitorPrice).filter(
            CompetitorPrice.is_current == True,
            CompetitorPrice.matched_product_id != None,
        ).all()

        for cp in competitor_prices:
            product = self.db.query(Product).get(cp.matched_product_id)
            if not product or not product.last_price:
                continue

            our_price = float(product.last_price)
            their_price = float(cp.price)

            if their_price >= our_price:
                continue

            savings_pct = ((our_price - their_price) / our_price) * 100
            if savings_pct < 5:
                continue

            if self._recommendation_exists('regional_price', product_id=product.id):
                continue

            store = self.db.query(CompetitorStore).get(cp.store_id)
            if not store:
                continue

            rec = Recommendation(
                type='regional_price',
                product_id=product.id,
                title=f"{product.name} cheaper at {store.name}",
                description=f"You pay ${our_price:.2f} but {store.name} has it for ${their_price:.2f} ({savings_pct:.0f}% less).",
                potential_savings=our_price - their_price,
                priority=4,
                data={'competitor_store_id': store.id, 'competitor_price': their_price, 'our_price': our_price},
                expires_at=datetime.now() + timedelta(days=7),
            )
            self.db.add(rec)
            count += 1

        return count

    def _check_volume_anomalies(self) -> int:
        """Flag products where recent purchase volume is 2x the average."""
        count = 0
        recent_cutoff = date.today() - timedelta(days=30)
        historical_cutoff = date.today() - timedelta(days=120)

        products = self.db.query(Product).all()

        for product in products:
            # Recent 30-day volume
            recent_vol = self.db.query(
                func.sum(ProductVendorPrice.quantity)
            ).filter(
                ProductVendorPrice.product_id == product.id,
                ProductVendorPrice.invoice_date >= recent_cutoff,
            ).scalar()

            if not recent_vol:
                continue

            # Historical 30-day average (90 days before that)
            historical_vol = self.db.query(
                func.sum(ProductVendorPrice.quantity)
            ).filter(
                ProductVendorPrice.product_id == product.id,
                ProductVendorPrice.invoice_date >= historical_cutoff,
                ProductVendorPrice.invoice_date < recent_cutoff,
            ).scalar()

            if not historical_vol:
                continue

            # Normalize to 30-day periods
            historical_monthly = float(historical_vol) / 3.0
            recent_monthly = float(recent_vol)

            if historical_monthly <= 0 or recent_monthly <= historical_monthly * 2:
                continue

            if self._recommendation_exists('volume_anomaly', product_id=product.id):
                continue

            ratio = recent_monthly / historical_monthly

            rec = Recommendation(
                type='volume_anomaly',
                product_id=product.id,
                title=f"Buying {ratio:.1f}x more {product.name}",
                description=f"You purchased {recent_monthly:.0f} units in the last 30 days vs. a historical average of {historical_monthly:.0f}/month. Verify this is intentional.",
                priority=5,
                data={'recent_volume': recent_monthly, 'historical_monthly': historical_monthly, 'ratio': ratio},
                expires_at=datetime.now() + timedelta(days=14),
            )
            self.db.add(rec)
            count += 1

        return count
