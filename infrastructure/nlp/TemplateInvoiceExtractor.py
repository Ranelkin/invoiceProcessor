import re
import yaml
import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
from models import TemplateGenerator

class TemplateInvoiceExtractor:
    """
    Invoice extractor that uses YAML templates exclusively.
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
    
    def extract_invoice_data(self, text: str, auto_generate: bool = False) -> Dict:
        """
        Extract invoice data using YAML templates only.
        
        Args:
            text: OCR'd invoice text
            auto_generate: If True, automatically generate template when none matches
            
        Returns:
            Dictionary with extracted fields and metadata
        """
        # First, try to identify the issuer from the document
        identified_issuer = self._identify_issuer(text)
        
        print(f"\nIssuer identification: {identified_issuer or 'Unable to identify'}")
        
        # Find matching template
        matched_template = self._match_template(text, identified_issuer)
        
        if not matched_template:
            if auto_generate and identified_issuer:
                print(f"\nGenerating new template for: {identified_issuer}")
                generator = TemplateGenerator()
                generator.generate_template(invoice_text=text, company_name=identified_issuer)
                # Reload templates and try again
                self.reload_templates()
                matched_template = self._match_template(text, identified_issuer)
            
            if not matched_template:
                return {
                    "error": "No matching template found",
                    "identified_issuer": identified_issuer,
                    "extraction_method": "none",
                    "template_used": None,
                    "confidence": 0.0,
                    "available_templates": list(self.templates.keys()),
                    "suggestion": f"Create a template for '{identified_issuer}' or enable auto_generate=True"
                }
        
        print(f"✓ Using template for: {matched_template['issuer']}")
        
        # Extract using template
        result = self._extract_with_template(text, matched_template)
        result["extraction_method"] = "template"
        result["template_used"] = matched_template['issuer']
        result["identified_issuer"] = identified_issuer
        
        # Calculate confidence
        result["confidence"] = self._calculate_confidence(result)
        
        return result
    
    def _identify_issuer(self, text: str) -> Optional[str]:
        """
        Attempt to identify the invoice issuer from the document.
        Looks in typical locations: header, "From:", "Issuer:", etc.
        
        Args:
            text: Invoice text
            
        Returns:
            Identified issuer name or None
        """
        lines = text.split('\n')
        text_lower = text.lower()
        
        # Strategy 1: Look for company name in first few lines (most common)
        # Many invoices start with company name/header
        header_lines = lines[:5]  # Check first 5 lines
        for line in header_lines:
            line_clean = line.strip()
            # Look for lines with company indicators
            company_indicators = [
                'gmbh', 'ag', 'inc', 'ltd', 'llc', 'corp', 'corporation',
                'aps', 'a/s', 'services', 'e.k', 'kg', 'ohg', 'co.'
            ]
            
            if any(indicator in line_clean.lower() for indicator in company_indicators):
                # Clean the line
                issuer = re.sub(r'[«»]', '', line_clean)  # Remove special chars
                issuer = re.sub(r'\s+', ' ', issuer).strip()
                
                # Validate: should be reasonable length
                if 5 <= len(issuer) <= 100 and not issuer.lower().startswith('invoice'):
                    print(f"✓ Identified issuer from header: {issuer}")
                    return issuer
        
        # Strategy 2: Look for explicit issuer indicators
        issuer_patterns = [
            r'(?:from|von|issuer|rechnungssteller|sender|absender)[:\s]+([A-Z][^\n]{3,50})',
            r'(?:billed?\s+by|rechnung\s+von)[:\s]+([A-Z][^\n]{3,50})',
            r'(?:invoice\s+from|rechnung\s+von)[:\s]+([A-Z][^\n]{3,50})',
        ]
        
        for pattern in issuer_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                issuer = match.group(1).strip()
                # Clean up and return
                issuer = re.sub(r'\s+', ' ', issuer)
                if 5 <= len(issuer) <= 100:  # Reasonable length
                    print(f"✓ Identified issuer from pattern: {issuer}")
                    return issuer
        
        # Strategy 2: Look in the first few lines (typical header location)
        # Use spaCy NER if available
        try:
            from util import extract_company_name
            # Check first 20% of document
            header_text = '\n'.join(lines[:max(1, len(lines) // 5)])
            company = extract_company_name(header_text)
            if company:
                print(f"✓ Identified issuer using NER: {company}")
                return company
        except Exception as e:
            print(f"  Note: NER issuer identification unavailable: {e}")
        
        # Strategy 3: Check against known template issuers in context
        for template_issuer in self.templates.keys():
            # Check if issuer appears near top of document with context clues
            top_section = '\n'.join(lines[:max(1, len(lines) // 5)])
            if template_issuer.lower() in top_section.lower():
                # Verify it's in issuer context, not recipient context
                recipient_patterns = [
                    r'(?:to|an|bill\s+to|rechnung\s+an|recipient|empfänger)[:\s]*.*?' + re.escape(template_issuer.lower()),
                ]
                
                is_recipient = any(re.search(p, top_section.lower(), re.IGNORECASE) 
                                  for p in recipient_patterns)
                
                if not is_recipient:
                    print(f"✓ Identified issuer from known templates: {template_issuer}")
                    return template_issuer
        
        print("  Could not confidently identify issuer")
        return None
    
    def _match_template(self, text: str, identified_issuer: Optional[str] = None) -> Optional[Dict]:
        """
        Match text against template keywords to find the right template.
        Uses a scoring system that prioritizes:
        1. Direct issuer match (if issuer was identified)
        2. Keywords appearing near the top of the document (likely issuer info)
        3. Multiple keyword matches
        4. Keywords NOT appearing in recipient context
        
        Args:
            text: Invoice text
            identified_issuer: Previously identified issuer name (if any)
            
        Returns:
            Matched template or None
        """
        text_lower = text.lower()
        lines = text_lower.split('\n')
        top_section = '\n'.join(lines[:max(1, len(lines) // 5)])
        
        # If issuer was identified, try exact match first
        if identified_issuer:
            issuer_lower = identified_issuer.lower()
            for template_issuer, template in self.templates.items():
                if template_issuer in issuer_lower or issuer_lower in template_issuer:
                    print(f"✓ Direct template match for identified issuer: {template['issuer']}")
                    return template
        
        best_match = None
        best_score = 0
        
        # Try to match each template with scoring
        for issuer, template in self.templates.items():
            keywords = template.get('keywords', [])
            if not keywords:
                continue
            
            score = 0
            matched_keywords = []
            
            # Check each keyword
            for keyword in keywords:
                keyword_lower = keyword.lower()
                
                if keyword_lower not in text_lower:
                    continue
                
                matched_keywords.append(keyword)
                
                # Base score for match
                score += 1
                
                # Check if keyword appears in recipient context (PENALTY)
                recipient_patterns = [
                    r'(?:to|an|bill\s+to|rechnung\s+an|recipient|empfänger|customer|kunde)[:\s]*.*?' + re.escape(keyword_lower),
                ]
                
                is_in_recipient_context = any(
                    re.search(p, text_lower, re.IGNORECASE | re.DOTALL) 
                    for p in recipient_patterns
                )
                
                if is_in_recipient_context:
                    # Heavy penalty - this is likely the wrong template
                    score -= 5
                    print(f"  ! Keyword '{keyword}' found in recipient context - penalizing")
                    continue
                
                # Bonus: keyword appears in first 20% of document (likely issuer section)
                if keyword_lower in top_section:
                    score += 3
                
                # Bonus: keyword appears near common issuer indicators
                issuer_context_patterns = [
                    r'(?:from|von|issuer|rechnungssteller|sender|absender)[:\s]*.*?' + re.escape(keyword_lower),
                    re.escape(keyword_lower) + r'.*?(?:invoice|rechnung|bill)',
                ]
                
                for pattern in issuer_context_patterns:
                    if re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL):
                        score += 4
                        break
            
            # Only consider if we have positive score and at least one keyword
            if score > 0 and len(matched_keywords) > 0:
                # Normalize score by keyword coverage
                normalized_score = score * (len(matched_keywords) / len(keywords))
                
                print(f"  Template '{template['issuer']}': {len(matched_keywords)}/{len(keywords)} keywords, score={normalized_score:.2f}")
                
                if normalized_score > best_score:
                    best_score = normalized_score
                    best_match = template
        
        # Only use template if score is significant (avoid weak matches)
        if best_match and best_score >= 2.0:
            print(f"✓ Selected template: {best_match['issuer']} (score: {best_score:.2f})")
            return best_match
        
        print("No confident template match found (threshold: 2.0)")
        return None
    
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
        
        # Extract data (with auto_generate option)
        print(text)
        result = extractor.extract_invoice_data(text, auto_generate=True)  # Enable auto-generation
        
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