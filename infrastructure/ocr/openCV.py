import cv2
import numpy as np
from pdf2image import convert_from_path
import img2pdf
from typing import List


def preprocess(f: str, dpi: int = 300) -> List[bytes]:
    """
    Preprocess PDF pages for optimal OCR performance.
    
    Args:
        f: Path to input PDF file
        dpi: Resolution for PDF conversion (default: 300)
    
    Returns:
        List of processed images as bytes
    """
    # Convert PDF pages to images with high quality
    pages = convert_from_path(f, dpi=dpi)
    processed_pages = []
    
    for page in pages:
        # Convert PIL Image to numpy array
        img = np.array(page)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        
        # 1. Denoise with optimized parameters
        denoised = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)
        
        # 2. Deskew the image
        deskewed = deskew_image(denoised)
        
        # 3. Enhance contrast using CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(deskewed)
        
        # 4. Sharpen the image
        sharpened = sharpen_image(enhanced)
        
        # 5. Apply adaptive thresholding with optimized parameters
        _, thresh = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # 6. Morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        # 7. Remove borders/noise at edges
        cleaned = remove_borders(cleaned)
        
        # Encode to bytes with high quality
        _, encoded = cv2.imencode('.png', cleaned, [cv2.IMWRITE_PNG_COMPRESSION, 1])
        processed_pages.append(encoded.tobytes())
    
    return processed_pages


def deskew_image(image: np.ndarray) -> np.ndarray:
    """Detect and correct skew in the image."""
    # Invert image for better edge detection
    inverted = cv2.bitwise_not(image)
    
    # Detect edges
    edges = cv2.Canny(inverted, 50, 150, apertureSize=3)
    
    # Detect lines using Hough transform
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
    
    if lines is not None:
        # Calculate angles
        angles = []
        for rho, theta in lines[:, 0]:
            angle = np.degrees(theta) - 90
            # Filter out outliers
            if -45 < angle < 45:
                angles.append(angle)
        
        if angles:
            # Use median angle for robustness
            median_angle = np.median(angles)
            
            # Only rotate if skew is significant (> 0.5 degrees)
            if abs(median_angle) > 0.5:
                # Rotate image
                (h, w) = image.shape
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                rotated = cv2.warpAffine(
                    image, M, (w, h),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE
                )
                return rotated
    
    return image


def sharpen_image(image: np.ndarray) -> np.ndarray:
    """Apply unsharp masking to sharpen text."""
    # Create Gaussian blur
    gaussian = cv2.GaussianBlur(image, (0, 0), 2.0)
    
    # Unsharp mask
    sharpened = cv2.addWeighted(image, 1.5, gaussian, -0.5, 0)
    
    return sharpened


def remove_borders(image: np.ndarray, border_size: int = 10) -> np.ndarray:
    """Remove noise at image borders."""
    h, w = image.shape
    
    # Create a mask for the border region
    mask = np.ones_like(image) * 255
    mask[:border_size, :] = 0  # Top
    mask[-border_size:, :] = 0  # Bottom
    mask[:, :border_size] = 0  # Left
    mask[:, -border_size:] = 0  # Right
    
    # Apply mask
    return cv2.bitwise_and(image, mask)


if __name__ == '__main__':
    import os 
    input_path =  os.environ.get("TEST_PATH")
    output_path = './Test_Output.pdf'
    
    print("Processing PDF...")
    out = preprocess(input_path, dpi=300)
    
    # Create and save PDF
    print("Creating output PDF...")
    with open(output_path, 'wb') as f:
        f.write(img2pdf.convert(out))
    
    print(f"✓ Processed {len(out)} pages")
    print(f"✓ Saved to: {output_path}")