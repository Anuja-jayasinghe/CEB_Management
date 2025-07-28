import cv2
import os
import numpy as np

def rotate_image(image, angle):
    """Rotate image by given angle"""
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, rotation_matrix, (w, h))
    return rotated

def preprocess_image(image_path, upload_folder='uploads'):
    """Enhanced preprocessing for meter reading extraction with better targeting"""
    img = cv2.imread(image_path)
    if img is None:
        return None

    height, width = img.shape[:2]
    
    # More focused cropping strategies specifically for meter displays
    crop_regions = [
        # Focus on the main digit display area (where 5-digit reading typically appears)
        img[int(height * 0.35):int(height * 0.65), int(width * 0.1):int(width * 0.9)],
        # Lower region (in case meter is positioned differently)
        img[int(height * 0.45):int(height * 0.75), int(width * 0.15):int(width * 0.85)],
        # Upper region (backup)
        img[int(height * 0.25):int(height * 0.55), int(width * 0.1):int(width * 0.9)],
        # Full center area
        img[int(height * 0.2):int(height * 0.8), int(width * 0.05):int(width * 0.95)]
    ]
    
    best_processed = None
    best_score = -1
    best_info = None
    
    for i, crop in enumerate(crop_regions):
        if crop.size == 0:
            continue
            
        # Convert to grayscale
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        
        # Try different orientations with emphasis on 180° for upside-down meters
        for angle in [0, 180, 90, 270]:  # Try 180° early since meters are often upside down
            rotated = rotate_image(gray, angle) if angle != 0 else gray
            
            # Enhanced preprocessing pipeline
            # 1. Noise reduction
            denoised = cv2.fastNlMeansDenoising(rotated)
            
            # 2. Contrast enhancement with stronger settings
            clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8,8))
            enhanced = clahe.apply(denoised)
            
            # 3. Multiple thresholding approaches with focus on digit clarity
            processed_versions = []
            
            # For dark digits on light background (normal)
            _, otsu_thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_versions.append(('normal_otsu', otsu_thresh))
            
            # For light digits on dark background (inverted) - common in LCD displays
            _, otsu_thresh_inv = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            processed_versions.append(('inverted_otsu', otsu_thresh_inv))
            
            # Adaptive thresholding - better for varying lighting
            adaptive_thresh = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                   cv2.THRESH_BINARY, 15, 4)
            processed_versions.append(('adaptive_normal', adaptive_thresh))
            
            # Inverted adaptive threshold
            adaptive_thresh_inv = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                       cv2.THRESH_BINARY_INV, 15, 4)
            processed_versions.append(('adaptive_inverted', adaptive_thresh_inv))
            
            # Morphological operations to clean up digits
            kernel = np.ones((2,2), np.uint8)
            for method_name, processed in processed_versions:
                # Clean up the image
                cleaned = cv2.morphologyEx(processed, cv2.MORPH_OPEN, kernel)
                cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)
                
                # Remove small noise
                cleaned = cv2.medianBlur(cleaned, 3)
                
                # Score this version
                score = score_image_quality(cleaned)
                
                if score > best_score:
                    best_score = score
                    best_processed = cleaned
                    best_info = f"crop_{i}_angle_{angle}_{method_name}"
                    
                    # Save the best version
                    processed_path = os.path.join(upload_folder, f'processed_best.jpg')
                    cv2.imwrite(processed_path, cleaned)
    
    return os.path.join(upload_folder, 'processed_best.jpg') if best_processed is not None else None

def score_image_quality(image):
    """Enhanced scoring for meter digit recognition"""
    # Find contours
    contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    score = 0
    digit_like_contours = 0
    digit_contours = []
    
    for contour in contours:
        area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)
        
        # Check if contour could be a digit
        if 200 < area < 8000:  # Reasonable digit size for meter displays
            aspect_ratio = float(w) / h
            if 0.2 < aspect_ratio < 1.8:  # Digit-like aspect ratio
                digit_like_contours += 1
                digit_contours.append((x, area, w, h))
                score += area * 0.1
    
    # Bonus for having 5 digit-like contours (expected for 5-digit meter)
    if digit_like_contours == 5:
        score += 1000
    elif 3 <= digit_like_contours <= 7:
        score += digit_like_contours * 100
    
    # Bonus for contours that are horizontally aligned (typical for meter displays)
    if len(digit_contours) >= 3:
        digit_contours.sort(key=lambda x: x[0])  # Sort by x position
        y_positions = [cv2.boundingRect(contours[i])[1] for i in range(len(contours)) 
                      if cv2.contourArea(contours[i]) > 200]
        
        if len(y_positions) >= 3:
            y_std = np.std(y_positions)
            if y_std < 20:  # Digits are well-aligned horizontally
                score += 300
    
    return score