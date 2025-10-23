from .InvoiceExtractor import InvoiceExtractor
from ..ocr import * 
import os 
from dotenv import load_dotenv

if __name__ == '__main__': 
    load_dotenv()
    p = os.environ.get("TEST_PATH")
    out = openCV.preprocess(p)
    text = document.ocr_document(out)
    extractor = InvoiceExtractor()
    res = extractor.extract_invoice_data(text)
    print(f"Extracted data: {res}")