#!/usr/bin/env python3
"""
Template-Based Invoice Extractor
Uses YAML templates exclusively for invoice data extraction
"""

import re
import yaml
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from models import TemplateGenerator
from util import extract_company_name
class TemplateInvoiceExtractor:
    """
    Invoice extractor that uses YAML templates exclusively.
    No fallback patterns - if no template matches, extraction fails gracefully.
    """
    
    def __init__(self, template_dir: str = "./templates"):
        """
        Args:
            template_dir: Directory containing YAML template files
        """
        self.template_dir = template_dir
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, Dict]:
        """Load all YAML templates from the template directory."""
        templates = {}
        
        if not os.path.exists(self.template_dir):
            print(f"Warning: Template directory '{self.template_dir}' not found")
            return templates
        
        for file_path in Path(self.template_dir).glob("*.yaml"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    template = yaml.safe_load(f)
                    
                    if template and 'issuer' in template:
                        # Store by issuer name (lowercase for matching)
                        issuer = template['issuer'].lower()
                        templates[issuer] = template
                        print(f"✓ Loaded template: {template['issuer']}")
            except Exception as e:
                print(f"✗ Error loading template {file_path}: {e}")
        
        print(f"\nTotal templates loaded: {len(templates)}")
        return templates
    
    def extract_invoice_data(self, text: str) -> Dict:
        """
        Extract invoice data using YAML templates only.
        
        Args:
            text: OCR'd invoice text
            
        Returns:
            Dictionary with extracted fields and metadata
        """
        # Find matching template
        matched_template = self._match_template(text)
        
        if not matched_template:
            return {
                "error": "No matching template found",
                "extraction_method": "none",
                "template_used": None,
                "confidence": 0.0,
                "available_templates": list(self.templates.keys())
            }
        
        print(f"✓ Using template for: {matched_template['issuer']}")
        
        # Extract using template
        result = self._extract_with_template(text, matched_template)
        result["extraction_method"] = "template"
        result["template_used"] = matched_template['issuer']
        
        # Calculate confidence
        result["confidence"] = self._calculate_confidence(result)
        
        return result
    
    def _match_template(self, text: str) -> Optional[Dict]:
        """
        Match text against template keywords to find the right template.
        
        Args:
            text: Invoice text
            
        Returns:
            Matched template or None
        """
        text_lower = text.lower()
        
        # Try to match each template
        for issuer, template in self.templates.items():
            keywords = template.get('keywords', [])
            
            # Count matching keywords
            matches = sum(1 for keyword in keywords if keyword.lower() in text_lower)
            
            # If at least one keyword matches, use this template
            if matches > 0:
                print(f"  Matched {matches}/{len(keywords)} keywords for '{template['issuer']}'")
                return template
        
        print("No template keywords matched")
        print("Create new template for the invoice type")
        extractor = TemplateGenerator()
        extractor.generate_template(invoice_text=text_lower, company_name="New Company")
        # Another recursive step for matching with the new template
        return self._match_template(text=text_lower)
    
    def _extract_with_template(self, text: str, template: Dict) -> Dict:
        """
        Extract all fields using a YAML template.
        
        Args:
            text: Invoice text
            template: YAML template dictionary
            
        Returns:
            Dictionary with extracted fields
        """
        result = {}
        fields = template.get('fields', {})
        options = template.get('options', {})
        
        # Extract issuer from template
        result['rechnungssteller'] = template.get('issuer')
        
        # Map template fields to our standard field names
        field_mapping = {
            'invoice_number': 'rechnungsnummer',
            'date': 'rechnungsdatum',
            'amount': 'rechnungsbetrag',
            'due_date': 'fälligkeitsdatum',
            'account_number': 'account_number',
            'vat': 'vat',
            'vat_rate': 'vat_rate',
            'currency': 'currency',
            'billing_period': 'billing_period',
            'service_charges': 'service_charges',
            'amount_no_vat': 'amount_no_vat'
        }
        
        # Extract invoice number
        result['rechnungsnummer'] = self._extract_field(
            text, 
            fields.get('invoice_number')
        )
        
        # Extract dates
        date_formats = options.get('date_formats', ['%B %d, %Y', '%d %B %Y', '%d.%m.%Y'])
        
        result['rechnungsdatum'] = self._extract_date_field(
            text,
            [fields.get('date'), fields.get('date_alt')],
            date_formats
        )
        
        result['fälligkeitsdatum'] = self._extract_date_field(
            text,
            [fields.get('due_date')],
            date_formats
        )
        
        # Extract amounts
        decimal_separator = options.get('decimal_separator', '.')
        
        result['rechnungsbetrag'] = self._extract_amount_field(
            text,
            fields.get('amount'),
            decimal_separator
        )
        
        # Extract services/line items
        result['leistungen'] = self._extract_lines(text, template.get('lines', []))
        
        # Extract additional fields
        result['account_number'] = self._extract_field(text, fields.get('account_number'))
        result['vat'] = self._extract_amount_field(text, fields.get('vat'), decimal_separator)
        result['vat_rate'] = self._extract_field(text, fields.get('vat_rate'))
        result['currency'] = self._extract_field(text, fields.get('currency'))
        result['billing_period'] = self._extract_field(text, fields.get('billing_period'))
        result['service_charges'] = self._extract_amount_field(text, fields.get('service_charges'), decimal_separator)
        result['amount_no_vat'] = self._extract_amount_field(text, fields.get('amount_no_vat'), decimal_separator)
        
        return result
    
    def _extract_field(self, text: str, pattern: Optional[str]) -> Optional[str]:
        """Extract a simple field using a regex pattern."""
        if not pattern:
            return None
        
        try:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                return value if value else None
        except Exception as e:
            print(f"  ✗ Pattern error: {e}")
        
        return None
    
    def _extract_date_field(self, text: str, patterns: List[Optional[str]], 
                           date_formats: List[str]) -> Optional[str]:
        """Extract and normalize a date field."""
        if not patterns:
            return None
        
        for pattern in patterns:
            if not pattern:
                continue
            
            try:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                if match:
                    date_str = match.group(1).strip()
                    
                    # Try to parse with provided formats
                    for fmt in date_formats:
                        try:
                            date_obj = datetime.strptime(date_str, fmt)
                            return date_obj.strftime('%d.%m.%Y')
                        except ValueError:
                            continue
                    
                    # If no format worked, try to normalize
                    return self._normalize_date(date_str)
            except Exception as e:
                print(f"  ✗ Date extraction error: {e}")
        
        return None
    
    def _extract_amount_field(self, text: str, pattern: Optional[str],
                              decimal_separator: str = '.') -> Optional[float]:
        """Extract and parse an amount field."""
        if not pattern:
            return None
        
        try:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if match:
                amount_str = match.group(1).strip()
                return self._parse_number(amount_str, decimal_separator)
        except Exception as e:
            print(f"  ✗ Amount extraction error: {e}")
        
        return None
    
    def _extract_lines(self, text: str, line_patterns: List[Any]) -> List[str]:
        """Extract line items/services using template patterns."""
        services = []
        
        if not line_patterns:
            return services
        
        for line_pattern in line_patterns:
            if isinstance(line_pattern, dict):
                description_pattern = line_pattern.get('description')
                
                if description_pattern:
                    try:
                        # Find all matches
                        matches = re.finditer(description_pattern, text, re.IGNORECASE | re.MULTILINE)
                        for match in matches:
                            # Try to get captured group, otherwise full match
                            if match.lastindex and match.lastindex >= 1:
                                service = match.group(1)
                            else:
                                service = match.group(0)
                            
                            service = service.strip()
                            
                            # Avoid duplicates
                            if service and service not in services:
                                services.append(service)
                    except Exception as e:
                        print(f"  ✗ Line extraction error: {e}")
        
        return services[:50]  # Limit to 50 items
    
    def _parse_number(self, num_str: str, decimal_separator: str = '.') -> Optional[float]:
        """
        Parse number string to float, handling various formats.
        
        Args:
            num_str: Number string (e.g., "1,234.56" or "1.234,56")
            decimal_separator: The decimal separator used ('.' or ',')
            
        Returns:
            Parsed float or None
        """
        try:
            # Remove spaces and non-breaking spaces
            num_str = num_str.replace(' ', '').replace('\xa0', '')
            
            if decimal_separator == '.':
                # English format: 1,234.56
                # Remove thousand separators (commas)
                num_str = num_str.replace(',', '')
                return float(num_str)
            else:
                # German format: 1.234,56
                # Remove thousand separators (dots) and replace comma with dot
                num_str = num_str.replace('.', '').replace(',', '.')
                return float(num_str)
        except ValueError:
            print(f"  ✗ Could not parse number: {num_str}")
            return None
    
    def _normalize_date(self, date_str: str) -> str:
        """Normalize date to DD.MM.YYYY format."""
        # Handle different separators
        date_str = date_str.replace('/', '.').replace('-', '.')
        parts = date_str.split('.')
        
        if len(parts) == 3:
            day, month, year = parts
            
            # Pad with zeros
            day = day.zfill(2)
            month = month.zfill(2)
            
            # Handle 2-digit years
            if len(year) == 2:
                year = '20' + year if int(year) < 50 else '19' + year
            
            return f"{day}.{month}.{year}"
        
        return date_str
    
    def _calculate_confidence(self, result: Dict) -> float:
        """
        Calculate confidence score based on extracted fields.
        
        Args:
            result: Extraction result dictionary
            
        Returns:
            Confidence score between 0 and 1
        """
        # Required fields (critical for an invoice)
        required_fields = ['rechnungsnummer', 'rechnungssteller', 'rechnungsbetrag']
        
        # Optional but important fields
        optional_fields = ['rechnungsdatum', 'fälligkeitsdatum', 'leistungen']
        
        # Count extracted required fields
        required_count = sum(1 for field in required_fields if result.get(field))
        required_score = required_count / len(required_fields)
        
        # Count extracted optional fields
        optional_count = sum(1 for field in optional_fields if result.get(field))
        optional_score = optional_count / len(optional_fields) if optional_fields else 0
        
        # Weight: 70% required, 30% optional
        confidence = (required_score * 0.7) + (optional_score * 0.3)
        
        return round(confidence, 2)
    
    def reload_templates(self):
        """Reload all templates from disk (useful after adding new templates)."""
        print("\n" + "="*50)
        print("Reloading templates...")
        print("="*50)
        self.templates = self._load_templates()


# Example usage
if __name__ == '__main__':
    from infrastructure.ocr import preprocess, ocr_document
    from dotenv import load_dotenv
    import os
    
    load_dotenv()
    
    # Initialize extractor
    extractor = TemplateInvoiceExtractor(template_dir='./templates')
    
    # Process invoice
    test_path = os.environ.get("TEST_PATH")
    if test_path:
        print("\n" + "="*50)
        print("Processing invoice...")
        print("="*50)
        
        # OCR the document
        processed_pages = preprocess(test_path)
        text = ocr_document(processed_pages)
        
        # Extract data
        print(text)
        result = extractor.extract_invoice_data(text)
        
        # Display results
        print("\n" + "="*50)
        print("EXTRACTION RESULTS")
        print("="*50)
        
        for key, value in result.items():
            if isinstance(value, list):
                print(f"\n{key}:")
                for item in value:
                    print(f"  - {item}")
            else:
                print(f"{key}: {value}")
    else:
        print("Please set TEST_PATH in your .env file")