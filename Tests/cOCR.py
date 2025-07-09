import cv2
import numpy as np
import re
import os
from PIL import Image
import requests
import json
import base64

class OptimizedMeterOCR:
    def __init__(self):
        self.crop_config = {
            # Based on your successful test - upper area crop
            "start_y_pct": 0.2,  # 20% from top
            "end_y_pct": 0.6,    # 60% from top  
            "start_x_pct": 0.1,  # 10% from left
            "end_x_pct": 0.9     # 90% from left
        }
    
    def preprocess_image(self, image_path):
        """Preprocess image for optimal OCR"""
        try:
            # Load image
            img = cv2.imread(image_path)
            if img is None:
                return None, "Could not load image"
            
            # Crop to display area first (this worked well in your test)
            height, width = img.shape[:2]
            start_y = int(height * self.crop_config["start_y_pct"])
            end_y = int(height * self.crop_config["end_y_pct"])
            start_x = int(width * self.crop_config["start_x_pct"])
            end_x = int(width * self.crop_config["end_x_pct"])
            
            cropped = img[start_y:end_y, start_x:end_x]
            
            # Convert to grayscale
            gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            
            # Light preprocessing (since online OCR worked well with minimal processing)
            # Just slight blur to reduce noise
            processed = cv2.GaussianBlur(gray, (3, 3), 0)
            
            return processed, "Success"
            
        except Exception as e:
            return None, str(e)
    
    def extract_meter_reading(self, ocr_text):
        """Extract meter reading from OCR text"""
        if not ocr_text:
            return None, "No text provided"
        
        # Clean the text
        lines = ocr_text.strip().split('\n')
        
        # Look for 5-digit number patterns (your meter reading format)
        for line in lines:
            # Remove extra spaces and clean
            clean_line = re.sub(r'\s+', ' ', line.strip())
            
            # Look for 5-digit patterns with optional decimal
            # Pattern: 15709 or 15709. or 1 5 7 0 9
            patterns = [
                r'(\d{5}\.?)',  # 15709 or 15709.
                r'(\d\s+\d\s+\d\s+\d\s+\d)',  # 1 5 7 0 9 (spaced)
                r'(\d{1,2}\.?\d{3,4}\.?)',  # 15.709 or similar
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, clean_line)
                if matches:
                    # Clean the match
                    reading = re.sub(r'[^\d]', '', matches[0])
                    if len(reading) == 5:  # Expected length
                        return reading, "Found 5-digit reading"
        
        # Fallback: extract all numbers and find 5-digit ones
        all_numbers = re.findall(r'\d+', ocr_text)
        five_digit_numbers = [num for num in all_numbers if len(num) == 5]
        
        if five_digit_numbers:
            return five_digit_numbers[0], "Found via fallback"
        
        return None, f"No 5-digit reading found in: {ocr_text}"
    
    def test_google_vision_api(self, image_path, api_key):
        """Test with Google Vision API"""
        try:
            # Preprocess image
            processed_img, status = self.preprocess_image(image_path)
            if processed_img is None:
                return None, f"Preprocessing failed: {status}"
            
            # Save processed image temporarily
            cv2.imwrite('temp_processed.jpg', processed_img)
            
            # Encode image
            with open('temp_processed.jpg', 'rb') as f:
                image_content = base64.b64encode(f.read()).decode('utf-8')
            
            # API call
            url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
            payload = {
                "requests": [{
                    "image": {"content": image_content},
                    "features": [{"type": "TEXT_DETECTION"}]
                }]
            }
            
            response = requests.post(url, json=payload)
            
            if response.status_code != 200:
                return None, f"API Error: {response.status_code}"
            
            result = response.json()
            
            # Clean up temp file
            if os.path.exists('temp_processed.jpg'):
                os.remove('temp_processed.jpg')
            
            if 'responses' in result and result['responses']:
                if 'textAnnotations' in result['responses'][0]:
                    detected_text = result['responses'][0]['textAnnotations'][0]['description']
                    return detected_text, "Success"
                else:
                    return None, "No text detected"
            else:
                return None, "Invalid API response"
                
        except Exception as e:
            return None, f"Error: {str(e)}"
    
    def test_reading_extraction(self, image_path, expected_reading, google_api_key=None):
        """Test the complete reading extraction process"""
        print(f"\n🔍 Testing Meter Reading Extraction")
        print(f"Image: {image_path}")
        print(f"Expected: {expected_reading}")
        print("=" * 50)
        
        # Check file exists
        if not os.path.exists(image_path):
            print(f"❌ File not found: {image_path}")
            return
        
        # Test preprocessing
        processed_img, status = self.preprocess_image(image_path)
        if processed_img is None:
            print(f"❌ Preprocessing failed: {status}")
            return
        
        # Save processed image for inspection
        cv2.imwrite('final_processed.jpg', processed_img)
        print(f"✅ Preprocessed image saved as 'final_processed.jpg'")
        
        # Test with Google Vision API if available
        if google_api_key:
            print(f"\n🔄 Testing Google Vision API...")
            ocr_text, status = self.test_google_vision_api(image_path, google_api_key)
            
            if ocr_text:
                print(f"✅ OCR Text extracted:")
                print(f"'{ocr_text}'")
                
                # Extract reading
                reading, extract_status = self.extract_meter_reading(ocr_text)
                
                if reading:
                    accuracy = "✅" if reading == expected_reading else "❌"
                    print(f"\n📊 Extracted Reading: {reading} {accuracy}")
                    print(f"Status: {extract_status}")
                else:
                    print(f"❌ Could not extract reading: {extract_status}")
            else:
                print(f"❌ OCR failed: {status}")
        else:
            print(f"\n📝 No Google API key provided")
            print(f"💡 Upload 'final_processed.jpg' to online OCR:")
            print(f"   - https://www.onlineocr.net/")
            print(f"   - https://www.newocr.com/")
            print(f"   - Copy the OCR text and test extraction manually")
    
    def manual_extraction_test(self, ocr_text, expected_reading):
        """Test extraction logic with OCR text"""
        print(f"\n🧪 Manual Extraction Test")
        print(f"OCR Text: '{ocr_text}'")
        print(f"Expected: {expected_reading}")
        print("=" * 30)
        
        reading, status = self.extract_meter_reading(ocr_text)
        
        if reading:
            accuracy = "✅" if reading == expected_reading else "❌"
            print(f"Extracted: {reading} {accuracy}")
            print(f"Status: {status}")
        else:
            print(f"❌ Extraction failed: {status}")

# Usage example
if __name__ == "__main__":
    ocr = OptimizedMeterOCR()
    
    # Test with your image
    image_file = "pic3.jpg"
    expected = "15709"
    
    # Test the complete process
    ocr.test_reading_extraction(image_file, expected)
    
    # Test extraction with your actual OCR result
    print("\n" + "="*60)
    your_ocr_text = """SHANGHAI JINLING INTELLIGENT ELECTRIC METER CO., LTD.
kW-h
15709.
10<sup>4</sup>
10<sup>3</sup>
10<sup>2</sup>
10<sup>1</sup>
1
0.1
H+C
®
IEC 521
ISO 9001"""
    
    ocr.manual_extraction_test(your_ocr_text, expected)