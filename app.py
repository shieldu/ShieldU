import threading
from flask import Flask, render_template_string, jsonify
from ultralytics import YOLO
import cv2
import datetime
import time
import platform
from flask import Flask, request, jsonify, render_template
from langchain_utils import LangChainHelper  # Langchain_utils.py for PDF processing
import os

# Windows-specific functionality for playing sound
if platform.system() == "Windows":
    import winsound

# YOLOv8s model
model = YOLO("yolov8s.pt")

# Intrusion logs and detection status
intrusion_log = []
intrusion_detected = False
is_running = False  # Control detection running status

# Open webcam feed
cap = cv2.VideoCapture(0)

# Flask app setup
app = Flask(__name__)

# HTML template for dynamic background color and logs
html_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Intrusion Detection Log</title>
    <style>
        body {
            {% if intrusion %}
                background-color: red;
            {% else %}
                background-color: white;
            {% endif %}
            transition: background-color 0.5s;
        }
    </style>
</head>
<body>
    <h1>실시간 침입자 감지 시스템 로그</h1>
    <button onclick="fetch('/start_detection')">침입자 감지 시작</button>
    <button onclick="fetch('/stop_detection')">침입자 감지 중지</button>
    <ul id="log-list">
        {% for log in logs %}
            <li>{{ log }}</li>
        {% endfor %}
    </ul>
    <script>
    function updateLogs() {
        fetch('/get_logs')
            .then(response => response.json())
            .then(data => {
                const logList = document.getElementById('log-list');
                logList.innerHTML = '';  // Clear the current log list
                data.logs.forEach(log => {
                    const li = document.createElement('li');
                    li.textContent = log;
                    logList.appendChild(li);
                });
            });
    }

    function checkIntrusionStatus() {
        fetch('/intrusion_status')
            .then(response => response.json())
            .then(data => {
                if (data.intrusion) {
                    document.body.style.backgroundColor = "red";
                } else {
                    document.body.style.backgroundColor = "white";
                }
            });
    }

    // Poll the server every second to check intrusion status and update logs
    setInterval(() => {
        checkIntrusionStatus();
        updateLogs();
    }, 1000);
    </script>
</body>
</html>
'''

# Route to display YOLO intrusion detection logs and control buttons
@app.route('/yolo')
def yolo():
    return render_template_string(html_template, logs=intrusion_log, intrusion=intrusion_detected)

# Route to get current intrusion status
@app.route('/intrusion_status')
def intrusion_status():
    return jsonify({"intrusion": intrusion_detected})

# Start detection route
@app.route('/start_detection')
def start_detection():
    global is_running
    is_running = True
    return jsonify({"status": "Detection started"})

# Stop detection route
@app.route('/stop_detection')
def stop_detection():
    global is_running
    is_running = False
    return jsonify({"status": "Detection stopped"})

# Route to get logs
@app.route('/get_logs')
def get_logs():
    return jsonify({"logs": intrusion_log})

# Function to continuously detect people using YOLO model
def detect_people():
    global intrusion_log, intrusion_detected, is_running

    while True:
        if not is_running:
            time.sleep(1)
            continue
        
        try:
            ret, frame = cap.read()
            if not ret:
                print("웹캠에서 프레임을 가져오지 못했습니다.")
                break

            # Run YOLO model to detect people
            results = model.predict(source=frame, show=True)
            intrusion_detected = False  # Reset intrusion status for each frame

            # Check if person is detected (COCO class ID 0)
            for result in results:
                for r in result.boxes.data:
                    class_id = int(r[-1])
                    if class_id == 0:  # Person detected
                        intrusion_detected = True
                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        log_entry = f"침입 감지: {timestamp}"
                        intrusion_log.append(log_entry)

                        # Play warning sound on Windows
                        if platform.system() == "Windows":
                            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)

            time.sleep(1)  # Add delay to reduce CPU usage
        except Exception as e:
            print(f"YOLO 감지 중 오류: {e}")

# Ensure the uploads folder exists for PDF uploads
if not os.path.exists('uploads'):
    os.makedirs('uploads')

# Create an instance of LangChainHelper for handling PDF processing and question answering
lc_helper = LangChainHelper()

# Route for the main home page
@app.route('/')
def home():
    return render_template('home.html')

# Route for the LangChain PDF chatbot page
@app.route('/langchain')
def langchain_page():
    return render_template('langchain.html')

# PDF upload API
@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    if 'pdf' not in request.files:
        return jsonify({"error": "파일을 선택해주세요."}), 400

    pdf_file = request.files['pdf']
    if pdf_file.filename == '':
        return jsonify({"error": "선택된 파일이 없습니다."}), 400

    lc_helper.process_pdf(pdf_file)  # Process PDF file using LangChainHelper
    return jsonify({"message": "PDF 파일이 성공적으로 업로드되었습니다."})

# API to ask a question and get an answer from the LangChain model
@app.route('/ask_question', methods=['POST'])
def ask_question():
    question = request.json.get('question')
    if not question:
        return jsonify({"error": "질문을 입력해주세요."}), 400

    answer = lc_helper.get_answer(question)  # Get answer from LangChainHelper
    return jsonify({"answer": answer})

# Function to run the YOLO detection in the background
def run_yolo_detection():
    yolo_thread = threading.Thread(target=detect_people)
    yolo_thread.daemon = True
    yolo_thread.start()
    print("YOLO 감지 스레드가 시작되었습니다.")

# Main function to run the server
if __name__ == '__main__':
    run_yolo_detection()  # Start YOLO detection thread
    app.run(debug=False, use_reloader=False)  # Run Flask server
