from flask import Flask, request, jsonify
from dotenv import load_dotenv
import cv2, os, re, requests
import numpy as np
from werkzeug.utils import secure_filename

# 🔑 Load environment variables from .env
load_dotenv()

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

OCR_API_KEY = os.getenv('OCR_API_KEY')
OCR_API_URL = 'https://api.ocr.space/parse/image'

print(f"OCR Key loaded: {OCR_API_KEY[:4]}******")

def rotate_image(image, angle):
    """Rotate image by given angle"""
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, rotation_matrix, (w, h))
    return rotated

def preprocess_image(image_path):
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
                    processed_path = os.path.join(UPLOAD_FOLDER, f'processed_best.jpg')
                    cv2.imwrite(processed_path, cleaned)
                    print(f"🎯 New best processing: {best_info} (score: {score:.2f})")
    
    # Save debug versions for manual inspection
    if best_processed is not None:
        print(f"🏆 Best processing method: {best_info}")
        
        # Save multiple versions for OCR fallback
        for i in range(min(2, len(crop_regions))):
            crop = crop_regions[i]
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            
            # Focus on 180-degree rotation for upside-down meters
            for angle in [0, 180]:
                rotated = rotate_image(gray, angle) if angle != 0 else gray
                
                denoised = cv2.fastNlMeansDenoising(rotated)
                clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8,8))
                enhanced = clahe.apply(denoised)
                
                # Create both normal and inverted versions
                _, thresh_normal = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                _, thresh_inverted = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                
                # Clean up
                kernel = np.ones((2,2), np.uint8)
                thresh_normal = cv2.morphologyEx(thresh_normal, cv2.MORPH_OPEN, kernel)
                thresh_inverted = cv2.morphologyEx(thresh_inverted, cv2.MORPH_OPEN, kernel)
                
                cv2.imwrite(os.path.join(UPLOAD_FOLDER, f'processed_{i}_r{angle}_normal.jpg'), thresh_normal)
                cv2.imwrite(os.path.join(UPLOAD_FOLDER, f'processed_{i}_r{angle}_inverted.jpg'), thresh_inverted)
    
    return os.path.join(UPLOAD_FOLDER, 'processed_best.jpg') if best_processed is not None else None

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

def extract_reading(ocr_text):
    """Enhanced extraction of 5-digit meter reading with better filtering"""
    if not ocr_text:
        return None
    
    print(f"🔍 Raw OCR text: '{ocr_text}'")
    
    # Clean the text with comprehensive character substitutions
    cleaned = ocr_text.replace('•', '').replace('*', '').replace('?', '').replace("'", '')
    cleaned = cleaned.replace('O', '0').replace('o', '0').replace('I', '1').replace('l', '1')
    cleaned = cleaned.replace('S', '5').replace('s', '5').replace('G', '6').replace('g', '6')
    cleaned = cleaned.replace('B', '8').replace('D', '0').replace('Z', '2').replace('E', '3')
    cleaned = cleaned.replace('A', '4').replace('T', '7').replace('U', '0').replace('C', '0')
    
    print(f"🔍 Cleaned OCR text: '{cleaned}'")
    
    # Split into lines for better analysis
    lines = cleaned.split('\n')
    candidates = []
    
    for line_idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        print(f"📝 Line {line_idx}: '{line}'")
        
        # Method 1: Look for 5 consecutive digits
        pattern1 = re.findall(r'\b\d{5}\b', line)
        for match in pattern1:
            candidates.append(('consecutive', match, line_idx, line))
            print(f"✅ Found 5-digit pattern: {match} in line {line_idx}")
        
        # Method 2: Look for spaced digits (common in meter displays)
        pattern2 = re.findall(r'(\d\s*\d\s*\d\s*\d\s*\d)', line)
        for match in pattern2:
            digits = re.sub(r'\s+', '', match)
            if len(digits) == 5:
                candidates.append(('spaced', digits, line_idx, line))
                print(f"✅ Found spaced digits: {digits} in line {line_idx}")
        
        # Method 3: Look for digits with separators
        pattern3 = re.findall(r'(\d[\s\-\.\,]*\d[\s\-\.\,]*\d[\s\-\.\,]*\d[\s\-\.\,]*\d)', line)
        for match in pattern3:
            digits = re.sub(r'[^\d]', '', match)
            if len(digits) == 5:
                candidates.append(('separated', digits, line_idx, line))
                print(f"✅ Found separated digits: {digits} in line {line_idx}")
        
        # Method 4: Extract all digits from this line if exactly 5
        line_digits = re.findall(r'\d', line)
        if len(line_digits) == 5:
            result = ''.join(line_digits)
            candidates.append(('exact_5', result, line_idx, line))
            print(f"✅ Found exactly 5 digits: {result} in line {line_idx}")
        
        # Method 5: For meter displays, look for digit sequences that might be separated by spaces or dots
        # This is common in LCD displays where digits are clearly separated
        meter_pattern = re.findall(r'(\d[\s\.\|]*\d[\s\.\|]*\d[\s\.\|]*\d[\s\.\|]*\d)', line)
        for match in meter_pattern:
            digits = re.sub(r'[^\d]', '', match)
            if len(digits) == 5:
                candidates.append(('meter_display', digits, line_idx, line))
                print(f"✅ Found meter display pattern: {digits} in line {line_idx}")
    
    # If no candidates found, try extracting from all text
    if not candidates:
        all_digits = re.findall(r'\d', cleaned)
        if len(all_digits) >= 5:
            result = ''.join(all_digits[:5])
            candidates.append(('first_5', result, -1, cleaned))
            print(f"✅ Using first 5 digits: {result}")
    
    # Enhanced filtering with better validation
    valid_candidates = []
    for method, reading, line_idx, source_line in candidates:
        # Skip readings that are all zeros or all ones (likely OCR errors)
        if reading == '00000' or reading == '11111':
            print(f"❌ Skipping invalid reading: {reading}")
            continue
        
        # Skip readings that start with many zeros (unlikely for active meters)
        if reading.startswith('000'):
            print(f"❌ Skipping reading with too many leading zeros: {reading}")
            continue
        
        # Skip readings that are all the same digit (likely OCR errors)
        if len(set(reading)) == 1:
            print(f"❌ Skipping reading with all same digits: {reading}")
            continue
            
        valid_candidates.append((method, reading, line_idx, source_line))
    
    if valid_candidates:
        print(f"🎯 Valid candidates found: {len(valid_candidates)}")
        for method, reading, line_idx, source_line in valid_candidates:
            print(f"   - {reading} (method: {method}, line: {line_idx})")
        
        # Prioritize by method reliability, with special focus on meter display patterns
        priority_order = ['meter_display', 'consecutive', 'exact_5', 'spaced', 'separated', 'first_5']
        
        for priority_method in priority_order:
            for method, reading, line_idx, source_line in valid_candidates:
                if method == priority_method:
                    print(f"🎯 Selected reading: {reading} (method: {method})")
                    return reading
        
        # If no priority match, return first valid candidate
        method, reading, line_idx, source_line = valid_candidates[0]
        print(f"🎯 Selected reading: {reading} (method: {method})")
        return reading
    
    print("❌ No valid reading found")
    return None

def ocr_space_request(image_path):
    """Make OCR request with enhanced settings"""
    try:
        with open(image_path, 'rb') as f:
            files = {'file': f}
            data = {
                'apikey': OCR_API_KEY,
                'language': 'eng',
                'scale': 'true',
                'OCREngine': '2',
                'detectOrientation': 'true',
                'isTable': 'false'
            }

            response = requests.post(OCR_API_URL, files=files, data=data)

        print("🌐 OCR.space status:", response.status_code)
        print("🔁 OCR.space raw response:", response.text)

        if response.status_code != 200:
            return None, "API Error"

        result = response.json()
        if result.get('OCRExitCode') == 1:
            text = result['ParsedResults'][0]['ParsedText']
            return text, None
        else:
            return None, result.get('ErrorMessage', 'Unknown OCR error')

    except Exception as e:
        print(f"❌ OCR request failed: {e}")
        return None, str(e)

def try_multiple_ocr_approaches(filepath):
    """Try OCR on multiple processed versions with enhanced fallback"""
    # Process the image with different approaches
    processed_path = preprocess_image(filepath)
    if not processed_path:
        return None, "Image preprocessing failed"
    
    all_readings = []
    
    # Try OCR on the best processed version
    ocr_text, error = ocr_space_request(processed_path)
    if not error:
        reading = extract_reading(ocr_text)
        if reading:
            all_readings.append(('best_processed', reading, ocr_text))
            print(f"🎯 Best processed result: {reading}")
    
    # Try OCR on alternative processed versions
    for i in range(2):  # Try first 2 crop regions
        for angle in [0, 180]:  # Focus on normal and upside-down
            for variant in ['normal', 'inverted']:
                alt_path = os.path.join(UPLOAD_FOLDER, f'processed_{i}_r{angle}_{variant}.jpg')
                if os.path.exists(alt_path):
                    ocr_text, error = ocr_space_request(alt_path)
                    if not error:
                        reading = extract_reading(ocr_text)
                        if reading:
                            all_readings.append((f'crop_{i}_r{angle}_{variant}', reading, ocr_text))
                            print(f"🎯 Alternative result: {reading} from {alt_path}")
    
    if not all_readings:
        return None, "Could not extract meter reading from any processed version"
    
    # Analyze all readings to find the most likely correct one
    print(f"📊 Found {len(all_readings)} potential readings:")
    for method, reading, ocr_text in all_readings:
        print(f"   - {reading} from {method}")
    
    # If we have multiple readings, use some heuristics to pick the best one
    if len(all_readings) > 1:
        # Count frequency of each reading
        reading_counts = {}
        for method, reading, ocr_text in all_readings:
            reading_counts[reading] = reading_counts.get(reading, 0) + 1
        
        # If one reading appears multiple times, prefer it
        most_common = max(reading_counts.items(), key=lambda x: x[1])
        if most_common[1] > 1:
            print(f"🏆 Most common reading: {most_common[0]} (appeared {most_common[1]} times)")
            return most_common[0], None
        
        # Otherwise, prefer readings that don't start with 0 or 1 (unless it's a very low reading)
        for method, reading, ocr_text in all_readings:
            if not reading.startswith('0') and not reading.startswith('1'):
                print(f"🏆 Preferred reading (doesn't start with 0/1): {reading}")
                return reading, None
    
    # Return the first valid reading
    method, reading, ocr_text = all_readings[0]
    print(f"🏆 Selected reading: {reading} from {method}")
    return reading, None

@app.route('/upload', methods=['POST'])
def upload():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    print(f"📸 Processing image: {filename}")

    # Try multiple OCR approaches
    reading, error = try_multiple_ocr_approaches(filepath)
    
    if reading:
        print(f"✅ Successfully extracted reading: {reading}")
        return jsonify({'meter_reading': reading}), 200
    else:
        print(f"❌ Failed to extract reading: {error}")
        return jsonify({'error': error}), 422

@app.route('/debug/<filename>')
def debug_processed(filename):
    """Debug endpoint to view processed images"""
    from flask import send_from_directory
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/debug/list')
def debug_list():
    """List all processed images for debugging"""
    try:
        files = os.listdir(UPLOAD_FOLDER)
        return jsonify({'files': files}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/test-ocr', methods=['POST'])
def test_ocr():
    """Test OCR on all processed versions for debugging"""
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    # Process the image
    processed_path = preprocess_image(filepath)
    if not processed_path:
        return jsonify({'error': 'Image preprocessing failed'}), 500
    
    results = []
    
    # Try OCR on all available processed versions
    for processed_file in os.listdir(UPLOAD_FOLDER):
        if processed_file.startswith('processed_') and processed_file.endswith('.jpg'):
            file_path = os.path.join(UPLOAD_FOLDER, processed_file)
            ocr_text, error = ocr_space_request(file_path)
            reading = extract_reading(ocr_text) if not error else None
            
            results.append({
                'file': processed_file,
                'ocr_text': ocr_text,
                'extracted_reading': reading,
                'error': error
            })
    
    return jsonify({'results': results}), 200

@app.route('/', methods=['GET'])
def home():
    return '📸 Enhanced OCR API is running!', 200

if __name__ == '__main__':
    app.run(debug=True)