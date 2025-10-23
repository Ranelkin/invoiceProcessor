#!/usr/bin/env python3
"""Improved Invoice Extractor - No spaCy version for testing."""

import re
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class InvoiceExtractor:
    """Improved invoice data extractor with better pattern matching."""
    
    def extract_invoice_data(self, text: str) -> Dict:
        """Extract all invoice fields with improved accuracy."""
        result = {
            "rechnungsnummer": self._extract_invoice_number(text),
            "rechnungssteller": self._extract_issuer(text),
            "rechnungsbetrag": self._extract_amount(text),
            "fälligkeitsdatum": self._extract_due_date(text),
            "leistungen": self._extract_services(text),
            "rechnungsdatum": self._extract_invoice_date(text),
        }
        
        return result
    
    def _extract_invoice_number(self, text: str) -> Optional[str]:
        """Extract invoice number with improved patterns."""
        patterns = [
            # Most explicit patterns first
            r'Invoice\s+no\.?[\s:]+([A-Z0-9\-/]+)',
            r'Rechnungsnummer[\s:]+([A-Z0-9\-/]+)',
            r'Rechnung(?:s)?(?:\s|-)?(?:Nr\.?|Nummer)[\s:]+([A-Z0-9\-/]+)',
            r'Invoice[\s\-]?(?:No\.?|Number)[\s:]+([A-Z0-9\-/]+)',
            r'Invoice\s+([A-Z0-9]{6,})',  # "Invoice 084000100446" format
            r'RE[\s\-]?Nr\.?[\s:]+([A-Z0-9\-/]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                number = match.group(1).strip()
                # Validate: should be alphanumeric, 4+ chars
                if len(number) >= 4 and re.match(r'^[A-Z0-9\-/]+$', number, re.IGNORECASE):
                    return number
        
        return None
    
    def _extract_issuer(self, text: str) -> Optional[str]:
        """Extract issuer company name and address - clean version."""
        lines = text.split('\n')
        
        # Strategy: Find company name with legal form in first 15 lines
        for i, line in enumerate(lines[:15]):
            line_stripped = line.strip()
            # Look for German company legal forms
            if re.search(r'\b(GmbH|AG|KG|UG|e\.V\.|OHG|Co\.|Ltd|Inc)\b', line_stripped, re.IGNORECASE):
                # Found a company name
                # Extract just the core company info (before contact details)
                # Split by bullet points or multiple spaces
                parts = re.split(r'[•·]|\s{3,}', line_stripped)
                
                # Get the company name and basic address (first few segments)
                company_parts = []
                for part in parts[:4]:  # Take up to 4 parts
                    part = part.strip()
                    # Skip if it looks like contact info
                    if re.search(r'Tel\.|Fax:|@|www\.', part, re.IGNORECASE):
                        break
                    if part:
                        company_parts.append(part)
                
                if company_parts:
                    return '\n'.join(company_parts)
        
        return None
    
    def _extract_amount(self, text: str) -> Optional[float]:
        """Extract total amount with support for € symbol and various formats."""
        patterns = [
            # "Amount due: € 36.21" format - highest priority
            r'Amount\s+due[\s:]*€?\s*([\d\s.,]+)\s*€?',
            # German formats
            r'(?:Gesamt|Total|Summe|Endbetrag|Rechnungsbetrag)(?:\s+brutto)?[\s:]*€?\s*([\d\s.,]+)\s*€?',
            r'(?:zu\s+zahlen|Zahlbetrag)[\s:]*€?\s*([\d\s.,]+)\s*€?',
            r'Endsumme[\s:]*€?\s*([\d\s.,]+)\s*€?',
            # Look for "Total" followed by amount
            r'Total[^\n€]{0,30}?€\s*([\d\s.,]+)',
        ]
        
        candidates = []
        
        for priority, pattern in enumerate(patterns):
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                amount_str = match.group(1).strip()
                try:
                    amount = self._parse_number(amount_str)
                    if amount > 0:
                        # Store with priority (lower is better) and position
                        candidates.append((amount, priority, match.start(), match.group(0)))
                except:
                    continue
        
        if candidates:
            # Sort by priority first, then by position (last occurrence wins for same priority)
            candidates.sort(key=lambda x: (x[1], x[2]))
            return candidates[0][0]
        
        return None
    
    def _extract_due_date(self, text: str) -> Optional[str]:
        """Extract due date or estimate from invoice date."""
        patterns = [
            r'(?:Fälligkeitsdatum|Fällig\s+am|Zahlbar\s+bis|Zahlungsziel)[\s:]*(\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4})',
            r'(?:Bitte\s+zahlen\s+bis|zu\s+zahlen\s+bis)[\s:]*(\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4})',
            r'(?:Due\s+date|Payment\s+due)[\s:]*(\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4})',
            r'Zahlung\s+bis[\s:]*(\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                return self._normalize_date(date_str)
        
        # Check for payment terms in days
        match = re.search(r'(?:Zahlungsziel|Zahlbar\s+in)[\s:]*(\d+)\s*Tag', text, re.IGNORECASE)
        if match:
            days = int(match.group(1))
            invoice_date = self._extract_invoice_date(text)
            if invoice_date:
                try:
                    date_obj = datetime.strptime(invoice_date, '%d.%m.%Y')
                    due_date_obj = date_obj + timedelta(days=days)
                    return due_date_obj.strftime('%d.%m.%Y')
                except:
                    pass
        
        # Check if invoice says "will be debited" (immediate payment)
        if re.search(r'will\s+(?:soon\s+)?be\s+debited', text, re.IGNORECASE):
            invoice_date = self._extract_invoice_date(text)
            return invoice_date if invoice_date else "Sofort fällig"
        
        return None
    
    def _extract_invoice_date(self, text: str) -> Optional[str]:
        """Extract invoice date."""
        patterns = [
            r'Invoice\s+date[\s:]*(\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4})',
            r'(?:Rechnungsdatum|Datum|Ausstellungsdatum)[\s:]*(\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self._normalize_date(match.group(1))
        
        return None
    
    def _extract_services(self, text: str) -> List[str]:
        """Extract itemized services with improved table parsing."""
        services = []
        
        # Strategy 1: Look for detailed line items table (like page 2)
        # The table has lines like: "1 1 Primary IPv4 Hours 532 € 0.0027 € 1.4364"
        
        # First, find lines that match the detailed item pattern
        lines = text.split('\n')
        in_items_section = False
        
        for line in lines:
            line_stripped = line.strip()
            
            # Start of detailed items section
            if re.match(r'Pos\s+count\s+Product', line_stripped, re.IGNORECASE):
                in_items_section = True
                continue
            
            # End of items section
            if re.match(r'Subtotal\s*\(excl', line_stripped, re.IGNORECASE):
                in_items_section = False
                continue
            
            # Skip section headers like "Dedicated Server (12/2024)"
            if re.match(r'^[A-Za-z\s]+\(\d{1,2}/\d{4}\)$', line_stripped):
                continue
            
            # Extract items in format: "1 1 Primary IPv4 Hours 532 € 0.0027 € 1.4364"
            if in_items_section and line_stripped:
                # Pattern: position, count, product name, unit, quantity, prices...
                match = re.match(
                    r'^\d+\s+\d+\s+(.+?)\s+(?:Hours?|Stk\.?|pcs|pieces|Stück|Units?)\s+\d',
                    line_stripped, re.IGNORECASE
                )
                
                if match:
                    service_name = match.group(1).strip()
                    if service_name and service_name not in services and len(service_name) > 2:
                        services.append(service_name)
        
        # Strategy 2: Look for overview table (like page 1)
        # Pattern: "Dedicated Server 12/2024 € 30.43 € 5.78A1 € 36.21"
        for line in lines:
            line_stripped = line.strip()
            
            # Match lines with service name + period + prices
            match = re.match(r'^([A-Za-z0-9\s\-]+?)\s+(\d{1,2}/\d{4})\s+€', line_stripped)
            if match:
                service_name = match.group(1).strip()
                # Avoid duplicates and generic words
                if (service_name and 
                    service_name not in services and 
                    len(service_name) > 3 and
                    not re.match(r'^(?:Total|Tax|Service|Period)$', service_name, re.IGNORECASE)):
                    services.append(service_name)
        
        return services[:50]
    
    def _parse_number(self, num_str: str) -> float:
        """Parse number in various formats."""
        # Remove spaces and non-breaking spaces
        num_str = num_str.replace(' ', '').replace('\xa0', '')
        
        # Count separators
        dot_count = num_str.count('.')
        comma_count = num_str.count(',')
        
        # Determine format
        if comma_count == 0 and dot_count <= 1:
            # English: 1234.56
            return float(num_str)
        elif dot_count == 0 and comma_count == 1:
            # German with comma: 1234,56
            return float(num_str.replace(',', '.'))
        elif dot_count >= 1 and comma_count == 1:
            # German: 1.234,56 or 12.345,67
            num_str = num_str.replace('.', '').replace(',', '.')
            return float(num_str)
        elif comma_count >= 1 and dot_count == 1:
            # English: 1,234.56
            num_str = num_str.replace(',', '')
            return float(num_str)
        else:
            # Default: try to clean up
            num_str = num_str.replace(',', '.')
            return float(re.sub(r'[^\d.]', '', num_str))
    
    def _normalize_date(self, date_str: str) -> str:
        """Normalize date to DD.MM.YYYY format."""
        # Handle different separators
        date_str = date_str.replace('/', '.').replace('-', '.')
        parts = date_str.split('.')
        
        if len(parts) == 3:
            # Assume DD.MM.YYYY for European invoices
            day, month, year = parts
            
            # Handle 2-digit years
            day = day.zfill(2)
            month = month.zfill(2)
            if len(year) == 2:
                year = '20' + year if int(year) < 50 else '19' + year
            
            return f"{day}.{month}.{year}"
        
        return date_str
    
    def _is_table_header(self, line: str) -> bool:
        """Check if line is a table header."""
        headers = [
            'pos', 'position', 'menge', 'quantity', 'qty',
            'unit price', 'price', 'betrag', 'amount',
            'description', 'product', 'service', 'period',
            'total', 'tax', 'unit', 'count', 'excl', 'vat'
        ]
        line_lower = line.lower()
        
        # Count header keywords
        keyword_count = sum(1 for h in headers if h in line_lower)
        
        # Must have multiple keywords and be relatively short
        return keyword_count >= 2 and len(line) < 150


