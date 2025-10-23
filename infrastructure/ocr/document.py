import pytesseract
from PIL import Image
import io
import re 
def ocr_page(image_bytes: bytes) -> str:
    # Convert bytes back to image
    img = Image.open(io.BytesIO(image_bytes))
    
    # Optimal config for documents/invoices
    # --oem 3: Use default OCR Engine Mode (LSTM + Legacy)
    # --psm 6: Assume a single uniform block of text
    # -c tessedit_char_whitelist: limit to specific characters (optional)
    custom_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
    
    text = pytesseract.image_to_string(img, config=custom_config, lang='eng')
    return text

def ocr_document(processed_pages: list[bytes]) -> str:
    full_text = []
    for i, page_bytes in enumerate(processed_pages, 1):
        print(f"Processing page {i}...")
        text = ocr_page(page_bytes)
        full_text.append(re.sub(r'\s+', ' ', text.strip()))
    return "\n\n--- PAGE BREAK ---\n\n".join(full_text)

if __name__ == '__main__':
    from .openCV import preprocess
    import os 
    p = os.environ.get("TEST_PATH")
    out = preprocess(p)
    text = ocr_document(out)
    print(f"Read in text:\n{text}")