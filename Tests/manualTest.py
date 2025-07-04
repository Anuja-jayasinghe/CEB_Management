import cv2
import numpy as np
import os

def manual_ocr_test(image_path):
    """Manual OCR test - just preprocess and show what OCR would see"""
    print(f"🔍 Manual OCR Test for: {image_path}")
    
    if not os.path.exists(image_path):
        print(f"❌ File not found: {image_path}")
        return
    
    # Load image
    img = cv2.imread(image_path)
    if img is None:
        print(f"❌ Could not load image")
        return
    
    print(f"✅ Image loaded: {img.shape}")
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply different preprocessing techniques
    techniques = {
        "original_gray": gray,
        "blurred": cv2.GaussianBlur(gray, (5, 5), 0),
        "threshold_otsu": cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
        "threshold_adaptive": cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2),
        "inverted": cv2.bitwise_not(cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1])
    }
    
    print(f"\n📸 Saving preprocessed versions:")
    for name, processed_img in techniques.items():
        filename = f"debug_{name}.jpg"
        cv2.imwrite(filename, processed_img)
        print(f"  - {filename}")
    
    # Try to crop display area
    height, width = img.shape[:2]
    
    # Estimate display area (adjust these percentages for your meter)
    crop_configs = [
        ("center", 0.3, 0.7, 0.2, 0.8),  # Center area
        ("upper", 0.2, 0.6, 0.1, 0.9),   # Upper area
        ("lower", 0.4, 0.8, 0.1, 0.9),   # Lower area
    ]
    
    print(f"\n✂️ Saving cropped versions:")
    for name, start_y_pct, end_y_pct, start_x_pct, end_x_pct in crop_configs:
        start_y = int(height * start_y_pct)
        end_y = int(height * end_y_pct)
        start_x = int(width * start_x_pct)
        end_x = int(width * end_x_pct)
        
        cropped = img[start_y:end_y, start_x:end_x]
        filename = f"debug_cropped_{name}.jpg"
        cv2.imwrite(filename, cropped)
        print(f"  - {filename}")
    
    print(f"\n🎯 WHAT TO DO NEXT:")
    print(f"1. Open all the debug_*.jpg files")
    print(f"2. Find the version where the numbers are clearest")
    print(f"3. Test that version with online OCR tools:")
    print(f"   - https://www.onlineocr.net/")
    print(f"   - https://www.newocr.com/")
    print(f"   - https://www.i2ocr.com/")
    print(f"4. Note which preprocessing works best")
    print(f"5. Expected reading: 15709")

if __name__ == "__main__":
    manual_ocr_test("pic3.jpg")