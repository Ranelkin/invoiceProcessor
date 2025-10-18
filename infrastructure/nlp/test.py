from .RobustInvoiceExtractor import RobustInvoiceExtractor
from ..ocr import * 
import os 
if __name__ == '__main__': 
    p = os.environ.get("TEST_PATH")
    out = openCV.preprocess(p)
    text = document.ocr_document(out)
    extractor = RobustInvoiceExtractor()
    res = extractor.extract_invoice_data(text)
    print(f"Extracted data: {res}")