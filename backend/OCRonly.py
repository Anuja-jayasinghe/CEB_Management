from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os, re, requests
from werkzeug.utils import secure_filename
import cv2

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

OCR_API_KEY = os.getenv('OCR_API_KEY')
OCR_API_URL = 'https://api.ocr.space/parse/image'

def extract_reading(ocr_text):
    """Enhanced extraction of 5-digit meter reading with better filtering"""
    if not ocr_text:
        return None
    
    # Clean the text with comprehensive character substitutions
    cleaned = ocr_text.replace('•', '').replace('*', '').replace('?', '').replace("'", '')
    cleaned = cleaned.replace('O', '0').replace('o', '0').replace('I', '1').replace('l', '1')
    cleaned = cleaned.replace('S', '5').replace('s', '5').replace('G', '6').replace('g', '6')
    cleaned = cleaned.replace('B', '8').replace('D', '0').replace('Z', '2').replace('E', '3')
    cleaned = cleaned.replace('A', '4').replace('T', '7').replace('U', '0').replace('C', '0')
    
    # Split into lines for better analysis
    lines = cleaned.split('\n')
    candidates = []
    
    for line_idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        # Method 1: Look for 5 consecutive digits
        pattern1 = re.findall(r'\b\d{5}\b', line)
        for match in pattern1:
            candidates.append(('consecutive', match, line_idx, line))
        
        # Method 2: Look for spaced digits (common in meter displays)
        pattern2 = re.findall(r'(\d\s*\d\s*\d\s*\d\s*\d)', line)
        for match in pattern2:
            digits = re.sub(r'\s+', '', match)
            if len(digits) == 5:
                candidates.append(('spaced', digits, line_idx, line))
        
        # Method 3: Extract all digits from this line if exactly 5
        line_digits = re.findall(r'\d', line)
        if len(line_digits) == 5:
            result = ''.join(line_digits)
            candidates.append(('exact_5', result, line_idx, line))
    
    # If no candidates found, try extracting from all text
    if not candidates:
        all_digits = re.findall(r'\d', cleaned)
        if len(all_digits) >= 5:
            result = ''.join(all_digits[:5])
            candidates.append(('first_5', result, -1, cleaned))
    
    # Filter out obviously invalid readings
    valid_candidates = []
    for method, reading, line_idx, source_line in candidates:
        if reading == '00000' or reading == '11111':
            continue
        if reading.startswith('000'):
            continue
        if len(set(reading)) == 1:
            continue
        valid_candidates.append((method, reading, line_idx, source_line))
    
    if valid_candidates:
        # Return the first valid candidate
        return valid_candidates[0][1]
    
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

        if response.status_code != 200:
            return None, "API Error"

        result = response.json()
        if result.get('OCRExitCode') == 1:
            text = result['ParsedResults'][0]['ParsedText']
            return text, None
        else:
            return None, result.get('ErrorMessage', 'Unknown OCR error')

    except Exception as e:
        return None, str(e)

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
    
    # Perform OCR directly on the uploaded image (no processing)
    ocr_text, error = ocr_space_request(filepath)
    
    if error:
        return jsonify({'error': error}), 422
    
    reading = extract_reading(ocr_text)
    
    if reading:
        return jsonify({'meter_reading': reading}), 200
    else:
        return jsonify({'error': 'Could not extract meter reading'}), 422

@app.route('/', methods=['GET'])
def home():
    return '📸 OCR API is running!', 200

if __name__ == '__main__':
    app.run(debug=True)