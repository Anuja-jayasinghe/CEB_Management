import requests
import cv2
import re
import os

class OCRSpaceTester:
    def __init__(self):
        self.results = []
    
    def preprocess_image(self, image_path):
        """Preprocess image for better OCR"""
        try:
            img = cv2.imread(image_path)
            if img is None:
                return None
            
            # Crop to upper area (based on your successful test)
            height, width = img.shape[:2]
            start_y = int(height * 0.2)
            end_y = int(height * 0.6)
            start_x = int(width * 0.1)
            end_x = int(width * 0.9)
            
            cropped = img[start_y:end_y, start_x:end_x]
            
            # Light preprocessing
            gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            processed = cv2.GaussianBlur(gray, (3, 3), 0)
            
            # Save processed image
            cv2.imwrite('processed_for_api.jpg', processed)
            return 'processed_for_api.jpg'
            
        except Exception as e:
            print(f"Preprocessing error: {e}")
            return None
    
    def ocr_space_api(self, image_path):
        """OCR.space API - Free tier: 25,000 requests/month"""
        try:
            processed_image = self.preprocess_image(image_path)
            if not processed_image:
                return "Preprocessing failed"
            
            print("🔄 Processing with OCR.space API...")
            
            # OCR.space API (free tier)
            url = 'https://api.ocr.space/parse/image'
            
            with open(processed_image, 'rb') as f:
                files = {'file': f}
                data = {
                    'apikey': 'K81765219388957',  # Free API key
                    'language': 'eng',
                    'detectOrientation': 'false',
                    'scale': 'true',
                    'OCREngine': '2'
                }
                
                response = requests.post(url, files=files, data=data)
            
            if response.status_code == 200:
                result = response.json()
                
                if result['OCRExitCode'] == 1:
                    text = result['ParsedResults'][0]['ParsedText']
                    print(f"✅ OCR result: {text}")
                    return text
                else:
                    print(f"❌ OCR error: {result['ErrorMessage']}")
                    return "OCR failed"
            else:
                print(f"❌ API error: {response.status_code}")
                return "API error"
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return f"Error: {str(e)}"
    
    def extract_meter_reading(self, ocr_text):
        """Extract 5-digit meter reading with improved logic"""
        if not ocr_text or ocr_text in ["Preprocessing failed", "OCR failed", "API error"]:
            return None
        
        print(f"🔍 Analyzing OCR text: '{ocr_text}'")
        
        # Clean the text - remove common OCR artifacts
        cleaned_text = ocr_text.replace('•', '').replace('*', '').replace('?', '').replace("'", '')
        print(f"🧹 Cleaned text: '{cleaned_text}'")
        
        # Strategy 1: Look for the first sequence of 5 digits (with possible spaces)
        # This handles cases like "1 5 7 0 9" or "15709"
        pattern1 = r'(\d\s*\d\s*\d\s*\d\s*\d)'
        matches1 = re.findall(pattern1, cleaned_text)
        
        if matches1:
            # Take the first match and remove spaces
            reading = re.sub(r'\s+', '', matches1[0])
            print(f"📍 Pattern 1 found: '{matches1[0]}' -> '{reading}'")
            if len(reading) == 5 and reading.isdigit():
                return reading
        
        # Strategy 2: Look for 5 consecutive digits
        pattern2 = r'(\d{5})'
        matches2 = re.findall(pattern2, cleaned_text)
        
        if matches2:
            reading = matches2[0]
            print(f"📍 Pattern 2 found: '{reading}'")
            return reading
        
        # Strategy 3: Extract all digits and try to form 5-digit reading
        # This is more aggressive - use with caution
        all_digits = re.findall(r'\d', cleaned_text)
        print(f"🔢 All digits found: {all_digits}")
        
        if len(all_digits) >= 5:
            # Try the first 5 digits
            reading = ''.join(all_digits[:5])
            print(f"📍 First 5 digits: '{reading}'")
            return reading
        
        print("❌ No valid 5-digit reading found")
        return None
    
    def process_meter_image(self, image_path, expected_reading=None):
        """Process meter image and extract reading"""
        print(f"🚀 Processing Meter Image")
        print(f"Image: {image_path}")
        if expected_reading:
            print(f"Expected: {expected_reading}")
        print("=" * 60)
        
        if not os.path.exists(image_path):
            print(f"❌ Image not found: {image_path}")
            return None
        
        # Get OCR result
        ocr_result = self.ocr_space_api(image_path)
        
        # Extract meter reading
        reading = self.extract_meter_reading(ocr_result)
        
        # Show result
        if expected_reading:
            accuracy = "✅" if reading == expected_reading else "❌"
            print(f"📊 Extracted: {reading} {accuracy}")
        else:
            print(f"📊 Extracted: {reading}")
        
        return reading

def main():
    tester = OCRSpaceTester()
    
    # Test your image
    image_file = "crops/debug_cropped_center.jpg"
    expected = "15709"
    
    result = tester.process_meter_image(image_file, expected)
    
    if result:
        print(f"\n✅ SUCCESS: Meter reading extracted: {result}")
        print(f"💡 OCR.space API: 25,000 free requests/month")
    else:
        print(f"\n❌ FAILED: Could not extract meter reading")

if __name__ == "__main__":
    main()