"""
Apple Tree Purchase Tracker - Invoice OCR Processor
Extracts structured data from invoice images
"""

import re
import json
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from pathlib import Path

# For production, we'd use:
# - pytesseract for local OCR
# - Google Cloud Vision API for better accuracy
# - Azure Form Recognizer for structured extraction

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


class InvoiceOCRProcessor:
    """
    Processes invoice images and extracts structured data.
    Supports multiple OCR backends and invoice formats.
    """
    
    # Common patterns for invoice parsing
    PATTERNS = {
        'invoice_number': [
            r'INV[#\-\s]*(\d+)',
            r'Invoice\s*[#:\-]?\s*(\w+)',
            r'Invoice\s*Number[:\s]+(\w+)',
            r'#\s*(\d{4,})'
        ],
        'date': [
            r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            r'Date[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})'
        ],
        'total': [
            r'Grand\s*Total[:\s]*\$?([\d,]+\.?\d*)',
            r'Total[:\s]*\$?([\d,]+\.?\d*)',
            r'Balance[:\s]*\$?([\d,]+\.?\d*)',
            r'Amount\s*Due[:\s]*\$?([\d,]+\.?\d*)'
        ],
        'phone': [
            r'(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})',
            r'\((\d{3})\)\s*(\d{3})[-.\s]?(\d{4})'
        ],
        'email': [
            r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        ]
    }
    
    # Known vendor patterns for auto-detection
    KNOWN_VENDORS = {
        'sj wellness': {
            'name': 'SJ Wellness',
            'category': 'Deli/Specialty',
            'patterns': ['sj wellness', 'sjwellness']
        },
        'krasdale': {
            'name': 'Krasdale',
            'category': 'Grocery/Dry Goods',
            'patterns': ['krasdale', 'krasdale foods']
        }
        # Add more vendors as needed
    }
    
    def __init__(self, ocr_backend: str = 'tesseract'):
        self.ocr_backend = ocr_backend
    
    def process_image(self, image_path: str) -> ExtractedInvoice:
        """
        Main entry point - process an invoice image and return extracted data.
        """
        # Get raw OCR text
        raw_text = self._perform_ocr(image_path)
        
        # Parse the text into structured data
        result = self._parse_invoice_text(raw_text)
        result.raw_text = raw_text
        
        return result
    
    def process_image_bytes(self, image_bytes: bytes, filename: str = '') -> ExtractedInvoice:
        """
        Process image from bytes (for API uploads).
        """
        # Save temporarily and process
        import tempfile
        suffix = Path(filename).suffix if filename else '.jpg'
        
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(image_bytes)
            temp_path = f.name
        
        try:
            return self.process_image(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def _perform_ocr(self, image_path: str) -> str:
        """
        Perform OCR on the image using configured backend.
        """
        if self.ocr_backend == 'tesseract':
            return self._ocr_tesseract(image_path)
        elif self.ocr_backend == 'google_vision':
            return self._ocr_google_vision(image_path)
        else:
            raise ValueError(f"Unknown OCR backend: {self.ocr_backend}")
    
    def _ocr_tesseract(self, image_path: str) -> str:
        """
        Use Tesseract for OCR.
        """
        try:
            import pytesseract
            from PIL import Image
            
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image)
            return text
        except ImportError:
            # Fallback for demo - return empty string
            print("Warning: pytesseract not installed, OCR disabled")
            return ""
    
    def _ocr_google_vision(self, image_path: str) -> str:
        """
        Use Google Cloud Vision API for OCR.
        Better accuracy but requires API key.
        """
        try:
            from google.cloud import vision
            
            client = vision.ImageAnnotatorClient()
            
            with open(image_path, 'rb') as f:
                content = f.read()
            
            image = vision.Image(content=content)
            response = client.text_detection(image=image)
            
            if response.text_annotations:
                return response.text_annotations[0].description
            return ""
        except ImportError:
            print("Warning: google-cloud-vision not installed")
            return ""
    
    def _parse_invoice_text(self, text: str) -> ExtractedInvoice:
        """
        Parse raw OCR text into structured invoice data.
        """
        result = ExtractedInvoice()
        
        if not text:
            return result
        
        lines = text.split('\n')
        lines = [l.strip() for l in lines if l.strip()]
        
        # Extract vendor info (usually at the top)
        result.vendor_name = self._extract_vendor_name(lines[:5])
        result.vendor_address = self._extract_address(lines[:5])
        result.vendor_phone = self._extract_pattern(text, 'phone')
        result.vendor_email = self._extract_pattern(text, 'email')
        
        # Extract invoice metadata
        result.invoice_number = self._extract_pattern(text, 'invoice_number')
        result.invoice_date = self._extract_pattern(text, 'date')
        result.total = self._extract_total(text)
        
        # Extract line items
        result.line_items = self._extract_line_items(lines)
        
        # Calculate confidence score
        result.confidence_score = self._calculate_confidence(result)
        
        return result
    
    def _extract_vendor_name(self, header_lines: List[str]) -> Optional[str]:
        """
        Extract vendor name from invoice header.
        """
        if not header_lines:
            return None
        
        # First non-empty line is often vendor name
        for line in header_lines:
            # Skip if it's clearly not a name
            if any(skip in line.lower() for skip in ['invoice', 'date', 'bill to', 'page']):
                continue
            
            # Check against known vendors
            line_lower = line.lower()
            for vendor_key, vendor_info in self.KNOWN_VENDORS.items():
                if any(p in line_lower for p in vendor_info['patterns']):
                    return vendor_info['name']
            
            # Return first reasonable line
            if len(line) > 2 and len(line) < 100:
                return line
        
        return None
    
    def _extract_address(self, header_lines: List[str]) -> Optional[str]:
        """
        Extract address from header.
        """
        address_pattern = r'\d+\s+[\w\s]+(?:rd|st|ave|blvd|dr|ln|way|ct|pl)[\s,]+[\w\s]+\d{5}'
        
        full_text = ' '.join(header_lines)
        match = re.search(address_pattern, full_text, re.IGNORECASE)
        
        if match:
            return match.group(0)
        return None
    
    def _extract_pattern(self, text: str, pattern_type: str) -> Optional[str]:
        """
        Extract using predefined patterns.
        """
        patterns = self.PATTERNS.get(pattern_type, [])
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1) if match.groups() else match.group(0)
        
        return None
    
    def _extract_total(self, text: str) -> Optional[float]:
        """
        Extract invoice total.
        """
        total_str = self._extract_pattern(text, 'total')
        if total_str:
            try:
                # Remove commas and convert
                return float(total_str.replace(',', ''))
            except ValueError:
                pass
        return None
    
    def _extract_line_items(self, lines: List[str]) -> List[ExtractedLineItem]:
        """
        Extract line items from invoice body.
        """
        items = []
        
        # Pattern for line items: number, product name, qty, rate, amount
        # Example: "1    Susie apple    1.00    38.00    38.00"
        line_item_pattern = r'^(\d+)\s+(.+?)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*$'
        
        # Alternative pattern: product, qty, rate, amount
        alt_pattern = r'^(.+?)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*$'
        
        line_num = 0
        for line in lines:
            # Skip header rows
            if any(h in line.lower() for h in ['product', 'qty', 'rate', 'amount', 'description', 'sr no']):
                continue
            
            # Try main pattern
            match = re.match(line_item_pattern, line)
            if match:
                line_num += 1
                items.append(ExtractedLineItem(
                    line_number=line_num,
                    product_name=match.group(2).strip(),
                    quantity=float(match.group(3)),
                    unit_price=float(match.group(4)),
                    total_price=float(match.group(5))
                ))
                continue
            
            # Try alternative pattern
            match = re.match(alt_pattern, line)
            if match:
                line_num += 1
                items.append(ExtractedLineItem(
                    line_number=line_num,
                    product_name=match.group(1).strip(),
                    quantity=float(match.group(2)),
                    unit_price=float(match.group(3)),
                    total_price=float(match.group(4))
                ))
        
        return items
    
    def _calculate_confidence(self, invoice: ExtractedInvoice) -> float:
        """
        Calculate a confidence score for the extraction.
        """
        score = 0.0
        max_score = 0.0
        
        # Vendor name
        max_score += 1
        if invoice.vendor_name:
            score += 1
        
        # Invoice number
        max_score += 1
        if invoice.invoice_number:
            score += 1
        
        # Date
        max_score += 1
        if invoice.invoice_date:
            score += 1
        
        # Total
        max_score += 1
        if invoice.total:
            score += 1
        
        # Line items
        max_score += 1
        if invoice.line_items and len(invoice.line_items) > 0:
            score += 1
        
        # Line items total matches invoice total
        if invoice.line_items and invoice.total:
            items_total = sum(item.total_price for item in invoice.line_items)
            if abs(items_total - invoice.total) < 0.01:
                score += 0.5
                max_score += 0.5
        
        return score / max_score if max_score > 0 else 0.0


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
            ExtractedLineItem(22, "(unlabeled)", 1.00, 52.00, 52.00),  # From "Please Note" row
        ],
        confidence_score=0.95
    )


# Demo/test
if __name__ == "__main__":
    # Test with manual parsing
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
    
    # Verify total
    items_total = sum(item.total_price for item in invoice.line_items)
    print(f"\nItems Total: ${items_total}")
    print(f"Invoice Total: ${invoice.total}")
    print(f"Match: {abs(items_total - invoice.total) < 0.01}")
