import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import cv2
import numpy as np
import matplotlib.pyplot as plt

# Configure Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def show_image(img, title="Image"):
    """Helper function to display images during debugging"""
    plt.imshow(img, cmap='gray')
    plt.title(title)
    plt.axis('off')
    plt.show()

def extract_meter_value(image_path):
    try:
        # 1. Load image
        img = Image.open(image_path)
        
        # 2. Crop to EXACT digit region (update these coordinates)
        img = img.crop((120, 60, 380, 140))  # Tight crop around digits
        
        # 3. Convert to grayscale and enhance
        img = img.convert('L')
        
        # 4. Apply adaptive thresholding
        img_np = np.array(img)
        img_np = cv2.adaptiveThreshold(img_np, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY_INV, 11, 2)
        
        # 5. Remove small noise
        kernel = np.ones((2,2), np.uint8)
        img_np = cv2.morphologyEx(img_np, cv2.MORPH_OPEN, kernel)
        
        # Debug: Show processed image
        show_image(img_np, "Processed Image for OCR")
        
        # 6. OCR with optimized settings
        custom_config = r'--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789.'
        text = pytesseract.image_to_string(Image.fromarray(img_np), config=custom_config)
        
        # 7. Clean results
        digits = ''.join(filter(str.isdigit, text))
        if not digits:
            # Fallback: Try different PSM mode
            custom_config = r'--psm 8 --oem 3 -c tessedit_char_whitelist=0123456789.'
            text = pytesseract.image_to_string(Image.fromarray(img_np), config=custom_config)
            digits = ''.join(filter(str.isdigit, text))
        
        return digits if digits else "OCR failed"
    
    except Exception as e:
        return f"Error: {str(e)}"

# Test with visualization
result = extract_meter_value("Test_1.jpg")
print(f"Final Result: {result}")