"""
Apple Tree Purchase Tracker - Invoice OCR Processor
Uses Claude Vision API (Anthropic SDK) for accurate invoice data extraction
"""

import os
import json
import base64
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class ExtractedLineItem:
    line_number: int
    product_name: str
    quantity: float
    unit_price: float
    total_price: float
    unit: Optional[str] = None
    product_code: Optional[str] = None
    confidence: float = 1.0


@dataclass
class ExtractedInvoice:
    vendor_name: Optional[str] = None
    vendor_address: Optional[str] = None
    vendor_phone: Optional[str] = None
    vendor_email: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    bill_to: Optional[str] = None
    ship_to: Optional[str] = None
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    line_items: List[ExtractedLineItem] = None
    raw_text: Optional[str] = None
    confidence_score: float = 0.0

    def __post_init__(self):
        if self.line_items is None:
            self.line_items = []

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['line_items'] = [asdict(item) for item in self.line_items]
        return result


VISION_PROMPT = """You are an expert invoice data extractor. Analyze this invoice image and extract all structured data.

Return ONLY valid JSON with this exact structure:
{
  "vendor_name": "string or null",
  "vendor_address": "string or null",
  "vendor_phone": "string or null",
  "vendor_email": "string or null",
  "invoice_number": "string or null",
  "invoice_date": "MM-DD-YYYY or null",
  "bill_to": "string or null",
  "subtotal": number or null,
  "tax": number or null,
  "total": number or null,
  "line_items": [
    {
      "line_number": 1,
      "product_name": "string",
      "quantity": number,
      "unit_price": number,
      "total_price": number,
      "unit": "string or null",
      "product_code": "string or null"
    }
  ]
}

Rules:
- Extract EVERY line item visible on the invoice
- For dates, use MM-DD-YYYY format
- For prices, use numeric values (no $ signs)
- If a field is not visible or unclear, use null
- product_name should be the full product description as written
- If quantity is not specified, assume 1.00
- total_price = quantity * unit_price (verify this)
- Return ONLY the JSON object, no markdown formatting"""


class InvoiceOCRProcessor:
    """
    Processes invoice images using Claude Vision API for accurate extraction.
    """

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")

    def process_image(self, image_path: str) -> ExtractedInvoice:
        """
        Process an invoice image file and return extracted data.
        """
        path = Path(image_path)
        if not path.exists():
            return ExtractedInvoice(confidence_score=0.0)

        image_bytes = path.read_bytes()
        return self._extract_with_claude(image_bytes, path.suffix.lower())

    def process_image_bytes(self, image_bytes: bytes, filename: str = '') -> ExtractedInvoice:
        """
        Process image from bytes (for API uploads).
        """
        suffix = Path(filename).suffix.lower() if filename else '.jpg'
        return self._extract_with_claude(image_bytes, suffix)

    def _get_media_type(self, suffix: str) -> str:
        media_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
        }
        return media_types.get(suffix, 'image/jpeg')

    def _extract_with_claude(self, image_bytes: bytes, suffix: str) -> ExtractedInvoice:
        """
        Send image to Claude Vision API and parse the response.
        """
        if not self.api_key:
            print("Warning: ANTHROPIC_API_KEY not set, OCR disabled")
            return ExtractedInvoice(confidence_score=0.0)

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key)
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            media_type = self._get_media_type(suffix)

            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": VISION_PROMPT,
                            },
                        ],
                    }
                ],
            )

            response_text = message.content[0].text
            return self._parse_claude_response(response_text)

        except Exception as e:
            print(f"Claude Vision error: {e}")
            return ExtractedInvoice(confidence_score=0.3, raw_text=str(e))

    def _parse_claude_response(self, response_text: str) -> ExtractedInvoice:
        """
        Parse Claude's JSON response into an ExtractedInvoice.
        """
        try:
            # Strip markdown code fences if present
            text = response_text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            data = json.loads(text)

            line_items = []
            for item in data.get("line_items", []):
                line_items.append(ExtractedLineItem(
                    line_number=item.get("line_number", len(line_items) + 1),
                    product_name=item.get("product_name", "Unknown"),
                    quantity=float(item.get("quantity", 1)),
                    unit_price=float(item.get("unit_price", 0)),
                    total_price=float(item.get("total_price", 0)),
                    unit=item.get("unit"),
                    product_code=item.get("product_code"),
                ))

            invoice = ExtractedInvoice(
                vendor_name=data.get("vendor_name"),
                vendor_address=data.get("vendor_address"),
                vendor_phone=data.get("vendor_phone"),
                vendor_email=data.get("vendor_email"),
                invoice_number=data.get("invoice_number"),
                invoice_date=data.get("invoice_date"),
                bill_to=data.get("bill_to"),
                subtotal=float(data["subtotal"]) if data.get("subtotal") is not None else None,
                tax=float(data["tax"]) if data.get("tax") is not None else None,
                total=float(data["total"]) if data.get("total") is not None else None,
                line_items=line_items,
                raw_text=response_text,
            )

            # Calculate confidence
            invoice.confidence_score = self._calculate_confidence(invoice)
            return invoice

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Failed to parse Claude response: {e}")
            return ExtractedInvoice(
                confidence_score=0.3,
                raw_text=response_text,
            )

    def _calculate_confidence(self, invoice: ExtractedInvoice) -> float:
        """
        Calculate confidence score based on extraction completeness.
        """
        checks = [
            invoice.vendor_name is not None,
            invoice.invoice_number is not None,
            invoice.invoice_date is not None,
            invoice.total is not None,
            len(invoice.line_items) > 0,
        ]

        base_score = sum(checks) / len(checks)

        # Bonus: line items total matches invoice total
        if invoice.line_items and invoice.total:
            items_total = sum(item.total_price for item in invoice.line_items)
            if abs(items_total - invoice.total) < 1.0:
                base_score = min(1.0, base_score + 0.1)

        # Map to confidence tiers: 0.95 for complete, 0.7 for partial
        if base_score >= 0.8:
            return 0.95
        elif base_score >= 0.5:
            return 0.7
        else:
            return 0.3


def parse_sj_wellness_invoice_manual() -> ExtractedInvoice:
    """
    Manual parsing of the SJ Wellness invoice from the image.
    This demonstrates what the OCR should extract.
    """
    return ExtractedInvoice(
        vendor_name="SJ Wellness",
        vendor_address="2 Atwood Rd, Plainview 11803",
        vendor_phone="7189624504",
        vendor_email="jimmychoi138@gmail.com",
        invoice_number="INV9568",
        invoice_date="02-02-2026",
        bill_to="Apple Tree",
        total=741.00,
        line_items=[
            ExtractedLineItem(1, "Susie apple", 1.00, 38.00, 38.00),
            ExtractedLineItem(2, "Susie's cookie banna coconut", 1.00, 38.00, 38.00),
            ExtractedLineItem(3, "Susie's cookie cranberry", 1.00, 38.00, 38.00),
            ExtractedLineItem(4, "Nutella family pack", 1.00, 60.00, 60.00),
            ExtractedLineItem(5, "Buneo white", 1.00, 32.00, 32.00),
            ExtractedLineItem(6, "Bueno", 1.00, 32.00, 32.00),
            ExtractedLineItem(7, "Tat Gluten Free Choco", 1.00, 52.00, 52.00),
            ExtractedLineItem(8, "Tates choco", 1.00, 52.00, 52.00),
            ExtractedLineItem(9, "Tru Fru Creamy Rasberry", 1.00, 30.00, 30.00),
            ExtractedLineItem(10, "Justin crispy dark", 1.00, 24.00, 24.00),
            ExtractedLineItem(11, "Quest bar peanutbutter cup", 1.00, 29.00, 29.00),
            ExtractedLineItem(12, "Off The Farm Apple Cinnamon", 1.00, 29.00, 29.00),
            ExtractedLineItem(13, "Off The Farm Bluberry", 1.00, 29.00, 29.00),
            ExtractedLineItem(14, "Off The Farm Peanutbutter", 1.00, 29.00, 29.00),
            ExtractedLineItem(15, "Barbell Birthday", 1.00, 29.00, 29.00),
            ExtractedLineItem(16, "Barbell Peanut Cream", 1.00, 26.00, 26.00),
            ExtractedLineItem(17, "Barbells Choco Dough", 1.00, 26.00, 26.00),
            ExtractedLineItem(18, "Barebell Peanut Caramel", 1.00, 26.00, 26.00),
            ExtractedLineItem(19, "Amphora Mango", 1.00, 26.00, 26.00),
            ExtractedLineItem(20, "Tates walnut", 1.00, 21.00, 21.00),
            ExtractedLineItem(21, "Tates oatmeal", 1.00, 52.00, 52.00),
            ExtractedLineItem(22, "(unlabeled)", 1.00, 52.00, 52.00),
        ],
        confidence_score=0.95
    )


if __name__ == "__main__":
    invoice = parse_sj_wellness_invoice_manual()

    print("Extracted Invoice:")
    print(f"  Vendor: {invoice.vendor_name}")
    print(f"  Address: {invoice.vendor_address}")
    print(f"  Invoice #: {invoice.invoice_number}")
    print(f"  Date: {invoice.invoice_date}")
    print(f"  Total: ${invoice.total}")
    print(f"  Items: {len(invoice.line_items)}")
    print(f"  Confidence: {invoice.confidence_score:.0%}")
    print()
    print("Line Items:")
    for item in invoice.line_items:
        print(f"  {item.line_number}. {item.product_name}: {item.quantity} x ${item.unit_price} = ${item.total_price}")

    items_total = sum(item.total_price for item in invoice.line_items)
    print(f"\nItems Total: ${items_total}")
    print(f"Invoice Total: ${invoice.total}")
    print(f"Match: {abs(items_total - invoice.total) < 0.01}")
