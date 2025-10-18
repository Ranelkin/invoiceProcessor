import spacy
import re
from typing import Dict, List, Optional
from datetime import datetime

class InvoiceExtractor:
    def __init__(self):
        """Initialize with spaCy German model."""
        try:
            self.nlp = spacy.load("de_core_news_lg")
            print("✓ spaCy German model loaded successfully")
        except OSError:
            print("Warning: German model not found. Installing...")
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", "de_core_news_lg"])
            self.nlp = spacy.load("de_core_news_lg")
    
    def extract_invoice_data(self, text: str) -> Dict:
        """Extract all invoice fields."""
        result = {
            "rechnungsnummer": self._extract_invoice_number(text),
            "rechnungssteller": self._extract_issuer(text),
            "rechnungsbetrag": self._extract_amount(text),
            "fälligkeitsdatum": self._extract_due_date(text),
            "leistungen": self._extract_services(text)
        }
        
        return result
    
    def _extract_invoice_number(self, text: str) -> Optional[str]:
        """Extract invoice number using multiple patterns."""
        patterns = [
            r'Rechnung(?:s)?(?:\s|-)?(?:Nr\.?|Nummer|Number)[\s:]*([A-Z0-9\-/]+)',
            r'Rechnungsnummer[\s:]+([A-Z0-9\-/]+)',
            r'Invoice[\s\-]?(?:No\.?|Number)[\s:]*([A-Z0-9\-/]+)',
            r'RE[\s\-]?Nr\.?[\s:]*([A-Z0-9\-/]+)',
            r'Beleg(?:\s|-)?Nr\.?[\s:]*([A-Z0-9\-/]+)',
            r'Rechnung\s+([A-Z0-9]{4,})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                number = match.group(1).strip()
                # Validate: should be alphanumeric, 4+ chars
                if len(number) >= 4 and re.match(r'^[A-Z0-9\-/]+$', number, re.IGNORECASE):
                    return number
        
        return None
    
    def _extract_issuer(self, text: str) -> Optional[str]:
        """Extract issuer using spaCy NER."""
        # Use spaCy to find organizations
        doc = self.nlp(text[:1500])  # Check first 1500 chars
        
        # Get all ORG entities
        orgs = [ent.text for ent in doc.ents if ent.label_ == 'ORG']
        
        if orgs:
            # Usually first ORG is the issuer
            issuer = orgs[0]
            
            # Try to extract full address block around the organization
            org_position = text.find(issuer)
            if org_position != -1:
                # Extract context around org name
                start = max(0, org_position - 50)
                end = min(len(text), org_position + 300)
                context = text[start:end]
                
                # Find the start of the address block
                lines_before = text[:org_position].split('\n')
                start_line = max(0, len(lines_before) - 2)
                
                # Extract address block
                all_lines = text.split('\n')
                address_lines = []
                
                for i in range(start_line, min(len(all_lines), start_line + 5)):
                    line = all_lines[i].strip()
                    if line and not self._is_section_header(line):
                        address_lines.append(line)
                    elif len(address_lines) > 2:
                        break
                
                if address_lines:
                    return '\n'.join(address_lines)
            
            return issuer
        
        # Fallback: look for common company patterns
        lines = text.split('\n')[:20]  # Check first 20 lines
        for i, line in enumerate(lines):
            line = line.strip()
            # Company names often have these markers
            if re.search(r'(GmbH|AG|KG|UG|e\.V\.|OHG|Co\.|Ltd)', line, re.IGNORECASE):
                # Collect this and next few lines for full address
                address_block = []
                for j in range(i, min(len(lines), i + 4)):
                    addr_line = lines[j].strip()
                    if addr_line and not self._is_section_header(addr_line):
                        address_block.append(addr_line)
                
                if address_block:
                    return '\n'.join(address_block)
        
        return None
    
    def _extract_amount(self, text: str) -> Optional[float]:
        """Extract total amount with high precision."""
        # Patterns for total amount
        patterns = [
            r'(?:Gesamt|Total|Summe|Endbetrag|Rechnungsbetrag|Betrag)(?:\s+brutto)?[\s:]*€?\s*([\d\s.,]+)\s*€?',
            r'(?:zu\s+zahlen|Zahlbetrag)[\s:]*€?\s*([\d\s.,]+)\s*€?',
            r'Gesamt(?:\s+inkl\.?\s+MwSt\.?)?[\s:]*€?\s*([\d\s.,]+)\s*€?',
            r'Endsumme[\s:]*€?\s*([\d\s.,]+)\s*€?',
            r'(?:Gesamtbetrag|Gesamtsumme)[\s:]*€?\s*([\d\s.,]+)\s*€?',
        ]
        
        candidates = []
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                amount_str = match.group(1)
                try:
                    # Convert German format (1.234,56 or 1 234,56) to float
                    amount = self._parse_german_number(amount_str)
                    if amount > 0:
                        candidates.append((amount, match.start()))
                except:
                    continue
        
        if candidates:
            # Return the last total found (usually the final amount)
            candidates.sort(key=lambda x: x[1])
            return candidates[-1][0]
        
        return None
    
    def _extract_due_date(self, text: str) -> Optional[str]:
        """Extract due date."""
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
        
        # Alternative: look for "Zahlungsziel" + days
        match = re.search(r'Zahlungsziel[\s:]*(\d+)\s*Tag', text, re.IGNORECASE)
        if match:
            days = int(match.group(1))
            invoice_date = self._extract_invoice_date(text)
            if invoice_date:
                try:
                    from datetime import timedelta
                    date_obj = datetime.strptime(invoice_date, '%d.%m.%Y')
                    due_date_obj = date_obj + timedelta(days=days)
                    return due_date_obj.strftime('%d.%m.%Y')
                except:
                    pass
        
        return None
    
    def _extract_invoice_date(self, text: str) -> Optional[str]:
        """Extract invoice date."""
        patterns = [
            r'(?:Rechnungsdatum|Datum|Ausstellungsdatum)[\s:]*(\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4})',
            r'(?:Invoice\s+date|Date)[\s:]*(\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self._normalize_date(match.group(1))
        
        return None
    
    def _extract_services(self, text: str) -> List[str]:
        """Extract itemized services/goods."""
        services = []
        
        # Find the itemized section
        section_headers = [
            r'(?:Position(?:en)?|Artikel|Leistung(?:en)?|Beschreibung|Posten)[\s:]*\n',
            r'Pos\.?\s+(?:Bezeichnung|Beschreibung|Artikel)',
            r'(?:Description|Item|Service)',
        ]
        
        section_start = None
        for pattern in section_headers:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                section_start = match.end()
                break
        
        if not section_start:
            return services
        
        # Find where itemized section ends
        section_end_markers = [
            r'\n\s*(?:Summe|Gesamt|Zwischensumme|Netto|Brutto|MwSt|Total|Subtotal)',
            r'\n\s*(?:Zahlungsbedingungen|Bankverbindung|Vielen\s+Dank|Geschäftsführer)',
        ]
        
        section_end = len(text)
        for pattern in section_end_markers:
            match = re.search(pattern, text[section_start:], re.IGNORECASE | re.MULTILINE)
            if match:
                section_end = section_start + match.start()
                break
        
        # Extract itemized section
        items_text = text[section_start:section_end]
        
        # Parse line items
        lines = items_text.split('\n')
        for line in lines:
            line = line.strip()
            
            # Skip empty lines, headers, and lines with only numbers/prices
            if not line or len(line) < 5:
                continue
            if re.match(r'^[\d\s\.,€]+$', line):
                continue
            if self._is_table_header(line):
                continue
            
            # Extract description (remove numbering and trailing prices)
            cleaned = re.sub(r'^\d+[\.\)]\s*', '', line)  # Remove position numbers
            cleaned = re.sub(r'\s+[\d.,]+\s*€?\s*$', '', cleaned)  # Remove trailing prices
            cleaned = re.sub(r'\s+\d+\s*$', '', cleaned)  # Remove trailing quantities
            
            if len(cleaned) > 3 and not re.match(r'^[\d\s\.,]+$', cleaned):
                services.append(cleaned.strip())
        
        return services[:20]  # Limit to 20 items
    
    def _parse_german_number(self, num_str: str) -> float:
        """Convert German number format to float."""
        # Remove all spaces
        num_str = num_str.replace(' ', '')
        # German format: 1.234,56 -> 1234.56
        # Remove thousand separators (dots)
        num_str = num_str.replace('.', '', num_str.count('.') - 1)
        # Replace decimal comma with dot
        num_str = num_str.replace(',', '.')
        return float(num_str)
    
    def _normalize_date(self, date_str: str) -> str:
        """Normalize date to DD.MM.YYYY format."""
        date_str = date_str.replace('/', '.').replace('-', '.')
        parts = date_str.split('.')
        
        if len(parts) == 3:
            day, month, year = parts
            day = day.zfill(2)
            month = month.zfill(2)
            if len(year) == 2:
                year = '20' + year if int(year) < 50 else '19' + year
            
            return f"{day}.{month}.{year}"
        
        return date_str
    
    def _is_section_header(self, line: str) -> bool:
        """Check if line is a section header."""
        headers = [
            'rechnung', 'invoice', 'position', 'artikel', 'leistung',
            'kunde', 'customer', 'zahlungsbedingung', 'bankverbindung',
            'summe', 'gesamt', 'total', 'mwst', 'steuer', 'lieferadresse',
            'rechnungsadresse'
        ]
        line_lower = line.lower()
        return any(header in line_lower for header in headers) and len(line) < 50
    
    def _is_table_header(self, line: str) -> bool:
        """Check if line is a table header."""
        headers = [
            'pos', 'menge', 'anzahl', 'einzelpreis', 'preis', 'betrag',
            'qty', 'quantity', 'price', 'amount', 'bezeichnung', 'beschreibung',
            'stk', 'einheit'
        ]
        line_lower = line.lower()
        # Must be short and contain header keywords
        return any(header in line_lower for header in headers) and len(line) < 100