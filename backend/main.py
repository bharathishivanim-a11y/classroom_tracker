import os
import sqlite3
import time
import threading
import csv
import io
from datetime import datetime
import numpy as np
import cv2
import face_recognition
from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import serial

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
KNOWN_FACES_DIR = os.path.join(BASE_PATH, "known_faces")
DB_PATH = os.path.join(BASE_PATH, "classroom.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        roll_number TEXT UNIQUE NOT NULL
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        date TEXT,
        entry_time TEXT,
        exit_time TEXT,
        status TEXT,
        FOREIGN KEY(student_id) REFERENCES students(id)
    )
    ''')
    conn.commit()
    conn.close()

init_db()

class SystemState:
    def __init__(self):
        self.trigger_active = None
        self.trigger_start_time = 0
        self.last_log_message = "System ready. Waiting for sensor inputs..."

state = SystemState()

class VideoCamera:
    def __init__(self):
        self.video = cv2.VideoCapture(0)
        self.current_frame = None
        self.known_face_encodings = []
        self.known_face_names = []
        self.load_known_faces()
        self.running = True
        
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()

    def _update_loop(self):
        global state
        while self.running:
            success, frame = self.video.read()
            if success:
                self.current_frame = frame
                
                if state.trigger_active:
                    if time.time() - state.trigger_start_time > 6.0:
                        state.last_log_message = f"Timeout: Face not detected for {state.trigger_active} operation."
                        state.trigger_active = None
                    else:
                        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
                        
                        face_locations = face_recognition.face_locations(rgb_small_frame)
                        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
                        
                        matched_name = None
                        for face_encoding in face_encodings:
                            matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding, tolerance=0.55)
                            if len(self.known_face_encodings) > 0:
                                face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
                                best_match = np.argmin(face_distances)
                                if matches[best_match]:
                                    matched_name = self.known_face_names[best_match]
                                    break
                        
                        if matched_name:
                            action = state.trigger_active
                            state.trigger_active = None
                            db_process_action(matched_name, action)
                            
            time.sleep(0.03)

    def load_known_faces(self):
        os.makedirs(KNOWN_FACES_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        self.known_face_encodings = []
        self.known_face_names = []
        
        for filename in os.listdir(KNOWN_FACES_DIR):
            if filename.lower().endswith((".jpg", ".png", ".jpeg")):
                path = os.path.join(KNOWN_FACES_DIR, filename)
                try:
                    image = face_recognition.load_image_file(path)
                    encodings = face_recognition.face_encodings(image)
                    if encodings:
                        name_raw = os.path.splitext(filename)[0]
                        name = name_raw.replace("_", " ")
                        
                        self.known_face_encodings.append(encodings[0])
                        self.known_face_names.append(name)
                        
                        cursor.execute("SELECT id FROM students WHERE name = ?", (name,))
                        if not cursor.fetchone():
                            roll = f"S{len(self.known_face_names):03d}"
                            cursor.execute("INSERT INTO students (name, roll_number) VALUES (?, ?)", (name, roll))
                            conn.commit()
                            print(f"Registered Student: {name} ({roll})")
                        print(f"Loaded encoding for: {name}")
                except Exception as e:
                    print(f"Error loading {filename}: {e}")
        conn.close()

    def get_frame_bytes(self):
        if self.current_frame is None:
            return None
        
        frame_disp = self.current_frame.copy()
        if state.trigger_active:
            cv2.rectangle(frame_disp, (10, 10), (320, 50), (0, 165, 255), -1)
            cv2.putText(frame_disp, f"SCANNING: {state.trigger_active}", (20, 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            
        ret, jpeg = cv2.imencode('.jpg', frame_disp)
        return jpeg.tobytes()

camera = None
try:
    camera = VideoCamera()
except Exception as e:
    print(f"Warning: Camera offline ({e})")

def db_process_action(name, action):
    global state
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, roll_number FROM students WHERE name = ?", (name,))
    row = cursor.fetchone()
    if not row:
        state.last_log_message = f"Error: Student '{name}' not found."
        conn.close()
        return
    
    student_id, student_name, roll = row[0], row[1], row[2]
    today = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M:%S")
    
    if action == "ENTRY":
        cursor.execute('''
            SELECT id FROM attendance 
            WHERE student_id = ? AND date = ? AND status = 'present'
        ''', (student_id, today))
        if cursor.fetchone():
            state.last_log_message = f"{student_name} ({roll}) is already marked inside."
        else:
            cursor.execute('''
                INSERT INTO attendance (student_id, date, entry_time, status)
                VALUES (?, ?, ?, 'present')
            ''', (student_id, today, now_time))
            conn.commit()
            state.last_log_message = f"ENTRY MATCH: {student_name} ({roll}) entered at {now_time}."
            
    elif action == "EXIT":
        cursor.execute('''
            SELECT id FROM attendance 
            WHERE student_id = ? AND date = ? AND status = 'present'
            ORDER BY id DESC LIMIT 1
        ''', (student_id, today))
        existing = cursor.fetchone()
        if existing:
            record_id = existing[0]
            cursor.execute('''
                UPDATE attendance 
                SET exit_time = ?, status = 'exited'
                WHERE id = ?
            ''', (now_time, record_id))
            conn.commit()
            state.last_log_message = f"EXIT MATCH: {student_name} ({roll}) left at {now_time}."
        else:
            state.last_log_message = f"EXIT BLOCKED: {student_name} had no entry log today."
            
    conn.close()

SERIAL_PORT = "COM3"
BAUD_RATE = 9600

def start_serial_listener():
    def loop():
        global state
        while True:
            try:
                ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
                print(f"Connected to Arduino on {SERIAL_PORT}")
                while True:
                    if ser.in_waiting > 0:
                        line = ser.readline().decode('utf-8').strip()
                        if line in ["ENTRY", "EXIT"]:
                            state.trigger_active = line
                            state.trigger_start_time = time.time()
                            state.last_log_message = f"Arduino trigger: Processing {line}..."
                    time.sleep(0.1)
            except Exception:
                time.sleep(5)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()

start_serial_listener()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/status")
def get_status():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute('''
        SELECT s.name, s.roll_number, a.entry_time 
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.date = ? AND a.status = 'present'
    ''', (today,))
    present = [dict(row) for row in cursor.fetchall()]

    cursor.execute('''
        SELECT name, roll_number FROM students
        WHERE id NOT IN (
            SELECT student_id FROM attendance 
            WHERE date = ? AND status = 'present'
        )
    ''', (today,))
    absent = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {
        "total_strength": len(present),
        "present": present,
        "absent": absent,
        "last_log": state.last_log_message
    }

@app.post("/api/trigger")
def manual_trigger(action: str = Query(..., regex="^(ENTRY|EXIT)$")):
    global state
    state.trigger_active = action
    state.trigger_start_time = time.time()
    state.last_log_message = f"Manual Web-Trigger: Scanning for {action}..."
    return {"status": "triggered", "action": action}

@app.get("/api/reload_faces")
def reload_faces():
    global camera
    if camera:
        camera.load_known_faces()
        return {"status": "success", "message": f"Faces synced. Registered matching: {len(camera.known_face_names)}"}
    return {"status": "error", "message": "Camera offline"}

def gen_frames():
    global camera
    while True:
        if camera is not None:
            frame = camera.get_frame_bytes()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.04)

@app.get("/api/video_feed")
def video_feed():
    return StreamingResponse(gen_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/export/{status_type}")
def export_csv(status_type: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    
    output = io.StringIO()
    writer = csv.writer(output)

    if status_type == "present":
        writer.writerow(["Student Name", "Roll Number", "Entry Time", "Status"])
        cursor.execute('''
            SELECT s.name, s.roll_number, a.entry_time 
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.date = ? AND a.status = 'present'
        ''', (today,))
        for r in cursor.fetchall():
            writer.writerow([r["name"], r["roll_number"], r["entry_time"], "Inside Classroom"])
        filename = f"present_students_{today}.csv"
    else:
        writer.writerow(["Student Name", "Roll Number", "Status"])
        cursor.execute('''
            SELECT name, roll_number FROM students
            WHERE id NOT IN (
                SELECT student_id FROM attendance 
                WHERE date = ? AND status = 'present'
            )
        ''', (today,))
        for r in cursor.fetchall():
            writer.writerow([r["name"], r["roll_number"], "Absent/Outside"])
        filename = f"absent_students_{today}.csv"

    conn.close()
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
