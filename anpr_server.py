import cv2
import numpy as np
import pytesseract
import json
import os
from flask import Flask, Response, render_template, jsonify, request
import threading
import time
import re

app = Flask(__name__, static_folder='static', template_folder='templates')

# Configuration
AUTHORIZED_PLATES_DICT = {
    "MH20EE7605": "Vehicle 1 - Authorized",
    "DL7CQ1939": "Vehicle 2 - Authorized",
    "UP72CB6066": "Vehicle 3 - Authorized",
    "GJ03ER0563": "Vehicle 4 - Authorized",
    "UP70DA3165": "Vehicle 5 - Authorized",
    "UP14ET6231": "Vehicle 6 - Authorized",
    "UP14LT1322": "Vehicle 7 - Authorized",
    "UP14LT2302": "Vehicle 8 - Authorized",
    "UP14LT6547": "Vehicle 9 - Authorized",
    "UP14LT9398": "Vehicle 10 - Authorized",
    "UP14LT0546": "Vehicle 11 - Authorized",
    "UP14LT2316": "Vehicle 12 - Authorized",
}

PLATE_DETECTION_INTERVAL = 0.5  # seconds between detection attempts
latest_detection = {"plate": None, "authorized": False, "timestamp": None, "confidence": 0, "description": ""}
detection_lock = threading.Lock()
debug_mode = True  # Set to True to see more detailed logs
scanning_enabled = True  # Global flag to control scanning

# Initialize camera
def get_camera():
    camera = cv2.VideoCapture(0)  # Use 0 for default webcam
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not camera.isOpened():
        raise RuntimeError("Could not open webcam. Please check connection.")
    return camera

# Preprocess image for better plate detection
def preprocess_image(image):
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply bilateral filter to preserve edges while reducing noise
    blur = cv2.bilateralFilter(gray, 11, 17, 17)
    
    # Apply adaptive thresholding
    thresh = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                  cv2.THRESH_BINARY_INV, 19, 9)
    
    # Apply morphological operations to remove small noise
    kernel = np.ones((3, 3), np.uint8)
    morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    morph = cv2.morphologyEx(morph, cv2.MORPH_OPEN, kernel)
    
    return morph

# Detect license plate in image
def detect_license_plate(image):
    # Make a copy of the original image for drawing and final extraction
    result_image = image.copy()
    
    # Preprocess the image
    processed = preprocess_image(image)
    
    # Find contours
    contours, _ = cv2.findContours(processed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    # Sort contours by area, largest first
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]
    
    # Initialize plate contour
    plate_contour = None
    
    # Loop through contours to find the best candidate for a license plate
    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        
        # If the contour has 4 points, it's likely a rectangle
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = float(w) / h
            
            # Check if aspect ratio matches typical license plates (2:1 to 6:1)
            if 2 < aspect_ratio < 6:
                plate_contour = approx
                break
    
    # If a plate contour was found
    if plate_contour is not None:
        x, y, w, h = cv2.boundingRect(plate_contour)
        
        # Add some padding around the plate
        padding = 5
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(image.shape[1] - x, w + 2 * padding)
        h = min(image.shape[0] - y, h + 2 * padding)
        
        return (x, y, w, h)
    
    return None

# Recognize text on the plate using OCR with improved preprocessing
def recognize_plate_text(image, plate_coords):
    if plate_coords is None:
        return None, 0
        
    x, y, w, h = plate_coords
    plate_img = image[y:y+h, x:x+w]
        
    # Resize the plate image (larger for better OCR)
    plate_img = cv2.resize(plate_img, (int(w * 3), int(h * 3)))
    
    # Convert to grayscale
    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    
    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    
    # Try multiple preprocessing approaches and combine results
    results = []
    confidences = []
    
    # Approach 1: Otsu thresholding
    _, thresh1 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Approach 2: Adaptive thresholding
    thresh2 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 11, 2)
    
    # Approach 3: Otsu thresholding with Gaussian blur
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh3 = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Save the processed images for debugging if needed
    if debug_mode:
        cv2.imwrite('last_plate_original.jpg', plate_img)
        cv2.imwrite('last_plate_thresh1.jpg', thresh1)
        cv2.imwrite('last_plate_thresh2.jpg', thresh2)
        cv2.imwrite('last_plate_thresh3.jpg', thresh3)
    
    # Try different OCR configurations
    configs = [
        '--psm 7 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',  # Single line
        '--psm 8 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',  # Single word
        '--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',  # Assume uniform block of text
    ]
    
    # Process each image with each config
    for img, img_name in [(thresh1, "Otsu"), (thresh2, "Adaptive"), (thresh3, "Gaussian+Otsu")]:
        for config in configs:
            text = pytesseract.image_to_string(img, config=config).strip()
            # Clean up the text (remove non-alphanumeric and normalize)
            text = ''.join(c for c in text if c.isalnum()).upper()
            
            if text and len(text) >= 4:  # Only consider results with at least 4 characters
                # Calculate confidence based on length and presence of expected patterns
                conf = min(len(text) / 10.0, 1.0)
                
                # Boost confidence for texts that match expected patterns
                # Indian plates often have patterns like XX00XX0000
                if re.match(r'^[A-Z]{2}\d{1,2}[A-Z]{1,2}\d{1,4}$', text):
                    conf += 0.3
                
                results.append(text)
                confidences.append(conf)
                
                if debug_mode:
                    print(f"OCR Result ({img_name}, {config}): '{text}', Confidence: {conf:.2f}")
    
    if not results:
        return None, 0
    
    # Find the result with highest confidence
    best_idx = confidences.index(max(confidences))
    best_text = results[best_idx]
    best_conf = confidences[best_idx]
    
    if debug_mode:
        print(f"Best OCR Result: '{best_text}', Confidence: {best_conf:.2f}")
    
    return best_text, best_conf

# Check if plate is authorized using dictionary lookup
def check_authorization(plate_text):
    if not plate_text:
        return False, ""
        
    # Convert to uppercase for case-insensitive matching
    plate_text = plate_text.upper()
    
    # Print for debugging
    if debug_mode:
        print(f"Checking if '{plate_text}' is authorized among: {list(AUTHORIZED_PLATES_DICT.keys())}")
    
    # Exact match
    if plate_text in AUTHORIZED_PLATES_DICT:
        if debug_mode:
            print(f"Exact match found for {plate_text}")
        return True, AUTHORIZED_PLATES_DICT[plate_text]
        
    # Check for close matches (allowing for OCR errors)
    for authorized_plate, description in AUTHORIZED_PLATES_DICT.items():
        # Calculate similarity (e.g., if only 1-2 characters are different)
        # For longer plates, we can allow more differences
        max_allowed_diff = max(1, len(authorized_plate) // 4)
        
        # Count matching characters in sequence
        matching_chars = 0
        for i in range(min(len(plate_text), len(authorized_plate))):
            if plate_text[i] == authorized_plate[i]:
                matching_chars += 1
        
        # Calculate similarity ratio
        similarity = matching_chars / max(len(plate_text), len(authorized_plate))
        
        # Check for partial matches (beginning of the plate)
        if len(plate_text) >= 4 and len(authorized_plate) >= 4:
            # If first 4+ characters match, it's likely the same plate
            prefix_match = plate_text[:4] == authorized_plate[:4]
            
            # If last 4+ characters match, it's likely the same plate
            suffix_match = False
            if len(plate_text) >= 4 and len(authorized_plate) >= 4:
                suffix_match = plate_text[-4:] == authorized_plate[-4:]
            
            if prefix_match or suffix_match:
                if debug_mode:
                    print(f"Partial match found: {plate_text} ~ {authorized_plate} (prefix/suffix match)")
                return True, description
        
        # If plates are very similar (e.g., 80% match)
        if similarity > 0.8 and abs(len(plate_text) - len(authorized_plate)) <= max_allowed_diff:
            if debug_mode:
                print(f"Close match found: {plate_text} ~ {authorized_plate} (similarity: {similarity:.2f})")
            return True, description
    
    if debug_mode:
        print(f"No match found for {plate_text}")
    return False, "Unauthorized Vehicle"

# Process frames for plate detection
def process_frame_for_detection(frame):
    global scanning_enabled
    
    # If scanning is disabled, just return the frame without processing
    if not scanning_enabled:
        return frame
    
    plate_coords = detect_license_plate(frame)
    
    if plate_coords:
        x, y, w, h = plate_coords
        plate_text, confidence = recognize_plate_text(frame, plate_coords)
        
        if plate_text and len(plate_text) >= 4 and confidence > 0.3:  # Lower threshold to 0.3
            authorized, description = check_authorization(plate_text)
            
            # Draw rectangle around plate
            color = (0, 255, 0) if authorized else (0, 0, 255)  # Green if authorized, red if not
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
            
            # Add text with better visibility
            status = "AUTHORIZED" if authorized else "UNAUTHORIZED"
            
            # Draw background rectangle for text
            text_size = cv2.getTextSize(f"{plate_text} - {status}", cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
            cv2.rectangle(frame, (x, y - 30), (x + text_size[0] + 10, y), color, -1)
            
            # Draw text
            cv2.putText(frame, f"{plate_text} - {status}", (x + 5, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                        
            # Update latest detection
            with detection_lock:
                global latest_detection
                latest_detection = {
                    "plate": plate_text,
                    "authorized": authorized,
                    "timestamp": time.time(),
                    "confidence": confidence,
                    "description": description
                }
    
    return frame

# Generate video frames
def generate_frames():
    camera = get_camera()
    last_detection_time = 0
    
    while True:
        success, frame = camera.read()
        if not success:
            break
            
        # Process for detection periodically to save resources
        current_time = time.time()
        if current_time - last_detection_time > PLATE_DETECTION_INTERVAL:
            frame = process_frame_for_detection(frame)
            last_detection_time = current_time
            
        # Encode the frame for streaming
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

# Flask routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/latest_detection')
def get_latest_detection():
    with detection_lock:
        return jsonify(latest_detection)

@app.route('/authorized_plates')
def get_authorized_plates():
    plates_with_descriptions = [{"plate": plate, "description": desc} for plate, desc in AUTHORIZED_PLATES_DICT.items()]
    return jsonify(plates_with_descriptions)

# Add a manual override route for testing
@app.route('/manual_authorize', methods=['POST'])
def manual_authorize():
    data = request.json
    plate = data.get('plate', '').upper()
    
    if not plate:
        return jsonify({"success": False, "message": "No plate provided"})
    
    authorized, description = check_authorization(plate)
    
    with detection_lock:
        global latest_detection
        latest_detection = {
            "plate": plate,
            "authorized": authorized,
            "timestamp": time.time(),
            "confidence": 1.0,  # Manual entry has perfect confidence
            "description": description
        }
    
    return jsonify({
        "success": True, 
        "plate": plate, 
        "authorized": authorized,
        "description": description
    })

# Toggle scanning route
@app.route('/toggle_scanning', methods=['POST'])
def toggle_scanning():
    global scanning_enabled
    data = request.json
    scanning_enabled = data.get('enabled', True)
    
    return jsonify({
        "success": True,
        "scanning": scanning_enabled
    })

if __name__ == '__main__':
    print(f"Starting ANPR server with {len(AUTHORIZED_PLATES_DICT)} authorized plates")
    app.run(host='0.0.0.0', port=5000, threaded=True)
