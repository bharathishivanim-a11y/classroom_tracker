# Smart Classroom Attendance System

This system tracks student entry and exit events using two ultrasonic sensors on an Arduino board, coupled with a dynamic computer-vision face-recognition backend.

File Structure details:
- classroom_tracker/arduino/classroom_detector.ino
- classroom_tracker/backend/main.py
- classroom_tracker/backend/requirements.txt
- classroom_tracker/frontend/index.html
- classroom_tracker/frontend/style.css
- classroom_tracker/frontend/script.js

Setup Guidelines:
1. Install dependencies from the requirements file inside backend/ directory.
2. Put images inside backend/known_faces/ using appropriate name mappings.
3. Upload the Arduino sketch and configure the corresponding backend COM port configuration inside main.py.
4. Launch uvicorn by starting main.py.
