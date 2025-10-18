import spacy
import re
from typing import Dict

# Load German language model
# Install with: python -m spacy download de_core_news_lg
nlp = spacy.load("de_core_news_lg")

def extract_invoice_data(text: str) -> Dict:
    doc = nlp(text)
    
    result = {
        "rechnungssteller": None,
        "rechnungsnummer": None,
        "datum": None,
        "liegenschaft": None,
        "leistungsbeschreibung": []
    }
    
    # Extract vendor/issuer (Rechnungssteller)
    # Look for organization names near top of document
    orgs = [ent.text for ent in doc.ents if ent.label_ == "ORG"]
    if orgs:
        result["rechnungssteller"] = orgs[0]  # Usually first ORG is vendor
    
    # Extract invoice number (Rechnungsnummer)
    # Common patterns: "Rechnung Nr. 12345", "Rechnungsnr: ABC-123"
    invoice_patterns = [
        r'Rechnung[s]?[\s-]?(?:Nr\.?|Nummer)[\s:]*([A-Z0-9\-/]+)',
        r'Invoice[\s-]?(?:No\.?|Number)[\s:]*([A-Z0-9\-/]+)',
        r'Rechnungsnummer[\s:]*([A-Z0-9\-/]+)'
    ]
    for pattern in invoice_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["rechnungsnummer"] = match.group(1)
            break
    
    # Extract date (Datum)
    # Look for dates near "Datum:", "Rechnungsdatum:", etc.
    date_patterns = [
        r'(?:Rechnung(?:s)?datum|Datum)[\s:]*(\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4})',
        r'(\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4})'
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            result["datum"] = match.group(1)
            break
    
    # Extract property (Liegenschaft)
    # Look for address-like patterns or specific keywords
    liegenschaft_keywords = [
        r'Liegenschaft[\s:]*([^\n]+)',
        r'Objekt[\s:]*([^\n]+)',
        r'Immobilie[\s:]*([^\n]+)'
    ]
    for pattern in liegenschaft_keywords:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["liegenschaft"] = match.group(1).strip()
            break
    
    # Extract service/product descriptions
    # Look for common section headers
    description_patterns = [
        r'(?:Leistung(?:en)?|Beschreibung|Position(?:en)?|Artikel)[\s:]*\n(.*?)(?=\n\n|Summe|Gesamt|Total)',
        r'(?:Service|Product)[\s:]*\n(.*?)(?=\n\n|Total|Amount)'
    ]
    for pattern in description_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            # Split by lines and clean up
            descriptions = [line.strip() for line in match.group(1).split('\n') if line.strip()]
            result["leistungsbeschreibung"] = descriptions
            break
    
    return result


