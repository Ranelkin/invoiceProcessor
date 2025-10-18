from .InvoiceExtractor import InvoiceExtractor
from typing import Dict, Optional, List
from datetime import datetime

class RobustInvoiceExtractor(InvoiceExtractor):
    """Enhanced extractor with validation and confidence scoring."""
    
    def extract_with_confidence(self, text: str) -> Dict:
        """Extract data with confidence scores."""
        result = self.extract_invoice_data(text)
        
        # Add confidence scores
        confidence = {
            "rechnungsnummer": self._confidence_invoice_number(text, result["rechnungsnummer"]),
            "rechnungssteller": self._confidence_issuer(text, result["rechnungssteller"]),
            "rechnungsbetrag": self._confidence_amount(text, result["rechnungsbetrag"]),
            "fälligkeitsdatum": self._confidence_date(result["fälligkeitsdatum"]),
            "leistungen": self._confidence_services(result["leistungen"])
        }
        
        result["confidence"] = confidence
        result["overall_confidence"] = sum(confidence.values()) / len(confidence)
        
        return result
    
    def _confidence_invoice_number(self, text: str, value: Optional[str]) -> float:
        if not value:
            return 0.0
        # High confidence if found with clear label
        import re
        if re.search(rf'Rechnungsnummer[\s:]+{re.escape(value)}', text, re.IGNORECASE):
            return 0.95
        return 0.75
    
    def _confidence_issuer(self, text: str, value: Optional[str]) -> float:
        if not value:
            return 0.0
        # Check if contains company markers
        import re
        if re.search(r'(GmbH|AG|KG|UG)', value):
            return 0.90
        return 0.70
    
    def _confidence_amount(self, text: str, value: Optional[float]) -> float:
        if not value:
            return 0.0
        return 0.85
    
    def _confidence_date(self, value: Optional[str]) -> float:
        if not value:
            return 0.0
        try:
            datetime.strptime(value, '%d.%m.%Y')
            return 0.90
        except:
            return 0.50
    
    def _confidence_services(self, services: List[str]) -> float:
        if not services:
            return 0.0
        if len(services) >= 1 and all(len(s) > 5 for s in services):
            return 0.85
        return 0.60