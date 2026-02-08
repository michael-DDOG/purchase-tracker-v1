"""
Apple Tree Purchase Tracker - Price Scraper
Scrapes competitor store websites for price comparison data.
"""

import re
import time
import random
from datetime import datetime
from typing import Optional, List, Dict, Any
from difflib import SequenceMatcher
from abc import ABC, abstractmethod

from sqlalchemy.orm import Session
from models import CompetitorStore, CompetitorPrice, Product


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
]


def normalize_product_name(name: str) -> str:
    """Normalize a product name for fuzzy matching."""
    name = name.lower().strip()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name


def fuzzy_match_product(name: str, products: List[Product], threshold: float = 0.6) -> Optional[Product]:
    """Find the best matching product using fuzzy string matching."""
    normalized = normalize_product_name(name)
    best_match = None
    best_score = 0.0

    for product in products:
        score = SequenceMatcher(None, normalized, product.normalized_name or "").ratio()
        if score > best_score and score >= threshold:
            best_score = score
            best_match = product

    return best_match


class PriceScraper(ABC):
    """Base class for price scrapers."""

    def __init__(self, store: CompetitorStore):
        self.store = store
        self.config = store.scraper_config or {}

    @abstractmethod
    async def scrape(self) -> List[Dict[str, Any]]:
        """
        Scrape prices from the store.
        Returns list of dicts with: product_name, price, unit (optional)
        """
        pass


class GenericWebScraper(PriceScraper):
    """
    CSS selector-based web scraper.
    Config should include:
    - url: page URL to scrape
    - product_selector: CSS selector for product containers
    - name_selector: CSS selector for product name within container
    - price_selector: CSS selector for price within container
    - unit_selector: (optional) CSS selector for unit
    - pages: (optional) number of pages to scrape
    - next_page_selector: (optional) CSS selector for next page link
    """

    async def scrape(self) -> List[Dict[str, Any]]:
        import httpx
        from bs4 import BeautifulSoup

        url = self.config.get('url')
        if not url:
            return []

        results = []
        headers = {"User-Agent": random.choice(USER_AGENTS)}

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')
                product_selector = self.config.get('product_selector', '.product')
                name_selector = self.config.get('name_selector', '.product-name')
                price_selector = self.config.get('price_selector', '.price')
                unit_selector = self.config.get('unit_selector')

                containers = soup.select(product_selector)

                for container in containers:
                    name_el = container.select_one(name_selector)
                    price_el = container.select_one(price_selector)

                    if not name_el or not price_el:
                        continue

                    name = name_el.get_text(strip=True)
                    price_text = price_el.get_text(strip=True)

                    # Extract numeric price
                    price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
                    if not price_match:
                        continue

                    price = float(price_match.group())
                    unit = None
                    if unit_selector:
                        unit_el = container.select_one(unit_selector)
                        if unit_el:
                            unit = unit_el.get_text(strip=True)

                    results.append({
                        'product_name': name,
                        'price': price,
                        'unit': unit,
                    })

                    # Rate limiting
                    time.sleep(random.uniform(0.1, 0.3))

        except Exception as e:
            print(f"Scrape error for {self.store.name}: {e}")

        return results


class ManualPriceScraper(PriceScraper):
    """
    No-op scraper for stores where prices are entered manually.
    """

    async def scrape(self) -> List[Dict[str, Any]]:
        return []


def get_scraper(store: CompetitorStore) -> PriceScraper:
    """Factory function to get the right scraper for a store."""
    scrapers = {
        'generic_web': GenericWebScraper,
        'manual': ManualPriceScraper,
    }
    scraper_class = scrapers.get(store.scraper_type, ManualPriceScraper)
    return scraper_class(store)


async def run_scraper(store: CompetitorStore, db: Session):
    """
    Run the scraper for a given store and save results to the database.
    """
    scraper = get_scraper(store)
    results = await scraper.scrape()

    if not results:
        return 0

    # Load all products for fuzzy matching
    products = db.query(Product).all()

    # Mark old prices as not current
    db.query(CompetitorPrice).filter(
        CompetitorPrice.store_id == store.id,
        CompetitorPrice.is_current == True
    ).update({CompetitorPrice.is_current: False})

    count = 0
    for item in results:
        normalized = normalize_product_name(item['product_name'])
        matched = fuzzy_match_product(item['product_name'], products)

        price = CompetitorPrice(
            store_id=store.id,
            product_name=item['product_name'],
            normalized_name=normalized,
            matched_product_id=matched.id if matched else None,
            price=item['price'],
            unit=item.get('unit'),
            is_current=True,
        )
        db.add(price)
        count += 1

    store.last_scraped_at = datetime.now()
    db.commit()

    return count
