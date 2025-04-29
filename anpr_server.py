from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import cv2
import threading
import time

app = Flask(__name__, static_url_path='/static')
CORS(app)

latest_plate = None
scanning_active = False

# Dummy list of authorized number plates
authorized_plates = ["MH12AB1234", "DL4CAF5031", "KA05MK1234"]

# Simulate a camera feed (replace with real ANPR logic)
def camera_loop():
    global latest_plate
    while True:
        if scanning_active:
            # Simulate plate detection every 5 seconds
            time.sleep(5)
            latest_plate = "MH12AB1234"  # Simulate detected plate
        else:
            time.sleep(1)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/authorized_plates')
def get_authorized_plates():
    return jsonify(authorized_plates)

@app.route('/latest_detection')
def get_latest_detection():
    if latest_plate:
        return jsonify({"plate": latest_plate, "authorized": latest_plate in authorized_plates})
    return jsonify({"plate": None, "authorized": False})

@app.route('/toggle_scanning', methods=['POST'])
def toggle_scanning():
    global scanning_active
    scanning_active = not scanning_active
    return jsonify({"scanning": scanning_active})

# Optional: Video streaming route
@app.route('/video')
def video():
    return app.send_static_file('video.mp4')  # Replace with real stream if needed

if __name__ == '__main__':
    threading.Thread(target=camera_loop, daemon=True).start()
    app.run(debug=True)
