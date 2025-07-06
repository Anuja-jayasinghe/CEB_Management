from flask import Flask, request, jsonify
from dotenv import load_dotenv
import cv2, os, re, requests
from werkzeug.utils import secure_filename

# 🔑 Load environment variables from .env
load_dotenv()

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

OCR_API_KEY = os.getenv('OCR_API_KEY')  # ✅ pulled from .env
OCR_API_URL = 'https://api.ocr.space/parse/image'

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

print(f"OCR Key loaded: {OCR_API_KEY[:4]}******")  # Optional
OCR_API_URL = 'https://api.ocr.space/parse/image'

def preprocess_image(image_path):
    """Crops and lightly preprocesses the image"""
    img = cv2.imread(image_path)
    if img is None:
        return None

    height, width = img.shape[:2]
    crop = img[int(height * 0.2):int(height * 0.6), int(width * 0.1):int(width * 0.9)]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    processed_path = os.path.join(UPLOAD_FOLDER, 'processed.jpg')
    cv2.imwrite(processed_path, gray)
    return processed_path

def extract_reading(ocr_text):
    """Extracts 5-digit number from OCR result"""
    cleaned = ocr_text.replace('•', '').replace('*', '').replace('?', '').replace("'", '')
    
    match1 = re.findall(r'(\d\s*\d\s*\d\s*\d\s*\d)', cleaned)
    if match1:
        digits = re.sub(r'\s+', '', match1[0])
        if len(digits) == 5:
            return digits

    match2 = re.findall(r'\b\d{5}\b', cleaned)
    if match2:
        return match2[0]

    digits_only = re.findall(r'\d', cleaned)
    if len(digits_only) >= 5:
        return ''.join(digits_only[:5])

    return None

def ocr_space_request(image_path):
    try:
        with open(image_path, 'rb') as f:
            files = {'file': f}
            data = {
                'apikey': OCR_API_KEY,
                'language': 'eng',
                'scale': 'true',
                'OCREngine': '2'
            }

            response = requests.post(OCR_API_URL, files=files, data=data)

        # ✅ NOW it's safe to print
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


@app.route('/upload', methods=['POST'])
def upload():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    processed_path = preprocess_image(filepath)
    if not processed_path:
        return jsonify({'error': 'Image preprocessing failed'}), 500

    ocr_text, error = ocr_space_request(processed_path)
    if error:
        return jsonify({'error': error}), 500

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
