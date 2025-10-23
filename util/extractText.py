import spacy

def extract_company_name(text: str) -> str:
    """
    Extracts the company name from the given string using spaCy's Named Entity Recognition (NER).
    Looks for entities labeled as 'ORG' (organization).
    Returns the first matching company name, or None if no match is found.
    
    Note: Requires spaCy and the 'de_core_news_sm' model to be installed.
    Install with: pip install spacy && python -m spacy download de_core_news_sm
    """
    nlp = spacy.load("de_core_news_sm")
    doc = nlp(text)
    
    for ent in doc.ents:
        if ent.label_ == "ORG":
            return ent.text
    
    return None