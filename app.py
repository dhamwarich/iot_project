import json
import os
import re
import glob
import time
import threading
import random
from typing import Optional, Dict, Any

# --- FASTAPI & SERVER IMPORTS ---
try:
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print("CRITICAL ERROR: Missing web libraries.")
    print("Please run: pip install fastapi uvicorn")
    exit(1)

# --- HARDWARE IMPORTS (With Fallback) ---
try:
    import serial  # pyserial
    SERIAL_AVAILABLE = True
except ImportError:
    serial = None
    SERIAL_AVAILABLE = False
    print("PySerial not found. Serial sensor data disabled.")

try:
    from gpiozero import Motor, DistanceSensor
    GPIO_AVAILABLE = True
except ImportError:
    print("gpiozero not found. Running motor/distance hardware in MOCK MODE.")
    GPIO_AVAILABLE = False
    Motor = DistanceSensor = None

HARDWARE_AVAILABLE = GPIO_AVAILABLE

# try:
# 	ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
#	ser.flush()
#	print("Connected to STM32. Ready to control LED")
# except:
# 	print("Error: Could not connect to /dev/ttyACM0. Is the USB plugged in?")
# 	exit()

# --- 1. Data Models & Config ---

FACES = {
    "awake": "0 ___ 0",
    "sleep": "- ___ -",
    "tired": "? ___ ?",
    "sad": "T ___ T",
}

class RobotState(BaseModel):
    light_val: Optional[int]
    soil_val: Optional[float]
    distance_cm: float
    current_face: str
    motor_state: str
    temperature_c: float
    gesture_label: Optional[str]
    gesture_mode: Optional[str]
    gesture_message: Optional[str]
    gesture_detected_at: Optional[str]


class GestureUpdate(BaseModel):
    gesture: Optional[str]
    mode: Optional[str]

# --- 2. Robot Controller ---

class RobotController:
    def __init__(self, port="/dev/ttyACM0", baudrate=115200):
        self.lock = threading.Lock()
        self._stop_event = threading.Event()
        
        # State initialization
        self.current_face: str = FACES["awake"]
        self.light_val: Optional[int] = 1
        self.soil_val: Optional[float] = 50.0
        self.distance: float = 0.0
        self.motor_state: str = "STOPPED"
        self.temperature_c: float = 24.0
        self.gesture_label: Optional[str] = None
        self.gesture_mode: Optional[str] = None
        self.gesture_message: Optional[str] = "No gesture detected"
        self.gesture_detected_at: Optional[str] = None

        # --- Hardware Setup ---
        self.serial_conn = None
        self.motor_right = None
        self.motor_left = None
        self.distance_sensor = None
        self.use_mock_hardware = not HARDWARE_AVAILABLE

        # Serial connection (independent of GPIO hardware)
        self.serial_conn = self._init_serial_connection(port, baudrate)

        # GPIO hardware setup (motors, ultrasonic)
        if GPIO_AVAILABLE and Motor and DistanceSensor:
            try:
                self.distance_sensor = DistanceSensor(echo=23, trigger=24)
                self.motor_right = Motor(forward=27, backward=22)
                self.motor_left = Motor(forward=16, backward=20)
                print("GPIO hardware initialized.")
            except Exception as exc:
                print(f"GPIO initialization failed ({exc}). Switching to mock drive mode.")
                self.use_mock_hardware = True
        else:
            self.use_mock_hardware = True

        if self.use_mock_hardware:
            print("--- RUNNING DRIVE HARDWARE IN MOCK MODE ---")

        # Start background thread
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _init_serial_connection(self, preferred_port, baudrate):
        if not SERIAL_AVAILABLE:
            print("PySerial unavailable. Install 'pyserial' to read STM32 data.")
            return None

        candidate_ports = []
        if preferred_port:
            candidate_ports.append(preferred_port)

        auto_ports = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
        for candidate in auto_ports:
            if candidate not in candidate_ports:
                candidate_ports.append(candidate)

        if not candidate_ports:
            print("✗ No serial devices (/dev/ttyACM* or /dev/ttyUSB*) found.")
            return None

        for candidate in candidate_ports:
            try:
                conn = serial.Serial(candidate, baudrate, timeout=1.0)
                time.sleep(0.1)  # Allow connection to stabilize
                conn.flush()
                conn.reset_input_buffer()
                print(f"✓ Serial connected on {candidate} @ {baudrate} bps")
                return conn
            except serial.SerialException as exc:
                print(f"✗ Serial port {candidate} unavailable ({exc}).")

        print("✗ Unable to open any serial ports. Running with mock data.")
        return None

    # --- Motor Abstractions ---

    def _set_motor_state(self, state_text):
        with self.lock:
            self.motor_state = state_text

    def stop_motors(self):
        if not self.use_mock_hardware:
            self.motor_right.stop()
            self.motor_left.stop()
        self._set_motor_state("STOPPED")

    def move_forward(self, speed=1.0):
        if not self.use_mock_hardware:
            self.motor_right.forward(speed)
            self.motor_left.forward(speed)
        self._set_motor_state(f"FORWARD ({speed})")

    def rotate(self, speed=1.0):
        if not self.use_mock_hardware:
            self.motor_left.forward(speed)
            self.motor_right.backward(speed)
        self._set_motor_state(f"ROTATING ({speed})")

    # --- Sensor Logic ---

    def _read_serial_packet(self):
        if not self.serial_conn:
            return {}

        try:
            # Check if data is available before reading
            if self.serial_conn.in_waiting == 0:
                return {}
            
            raw = self.serial_conn.readline().decode("utf-8", errors="replace").strip()
            if not raw:
                return {}

            # Debug: Print raw data (comment out after testing)
            print(f"[SERIAL] Raw: {raw}")

            # Try JSON payload first
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    result = {str(k).strip().lower(): parsed[k] for k in parsed}
                    print(f"[SERIAL] Parsed JSON: {result}")
                    return result
            except json.JSONDecodeError:
                pass

            # Fallback: key:value comma-separated string
            cleaned = raw.replace("[", "").replace("]", "")
            packet = {}
            for part in cleaned.split(","):
                if ":" not in part:
                    continue
                key, value = part.split(":", 1)
                packet[key.strip().lower()] = value.strip()
            
            if packet:
                print(f"[SERIAL] Parsed key-value: {packet}")
            return packet
        except Exception as e:
            print(f"[SERIAL] Error reading: {e}")
            return {}

    @staticmethod
    def _coerce_numeric(value):
        if isinstance(value, (int, float)):
            return float(value)
        match = re.search(r"-?\d+(?:\.\d+)?", str(value))
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None
        return None

    def _extract_serial_number(self, packet, keys, as_int=False):
        for key in keys:
            if key in packet:
                number = self._coerce_numeric(packet[key])
                if number is not None:
                    return int(number) if as_int else float(number)
        return None

    def _read_sensors(self):
        """Reads real hardware or generates mock data."""

        packet = self._read_serial_packet()

        # Distance from STM32 payload (fallback to GPIO sensor, then mock)
        dist_cm = self._extract_serial_number(packet, (
            "distance", "distance_cm", "range", "distance (cm)"
        ))

        if dist_cm is None and not self.use_mock_hardware and self.distance_sensor:
            dist_cm = self.distance_sensor.distance * 100
        elif dist_cm is None and self.distance:
            dist_cm = self.distance
        elif dist_cm is None:
            dist_cm = random.uniform(10, 100)

        # Light & soil moisture from serial
        l_val = self._extract_serial_number(packet, (
            "light", "light_val", "light detected", "lightdetected"
        ), as_int=True)
        s_val = self._extract_serial_number(packet, (
            "soil", "soil_val", "soil humidity", "soil_humidity"
        ))

        if l_val is None and s_val is None and (not packet) and not self.serial_conn:
            # No serial hardware at all -> mock light/soil
            l_val = self.light_val
            if random.random() > 0.95:
                l_val = 1 if l_val == 0 else 0
            s_val = self.soil_val
            change = random.uniform(-2, 2)
            s_val = max(0, min(100, (s_val or 50.0) + change))
        else:
            if l_val is None:
                l_val = self.light_val
            if s_val is None:
                s_val = self.soil_val

        # Temperature (prefer serial, otherwise jitter existing mock)
        temp = self._extract_serial_number(packet, (
            "temperature", "temperature_c", "temp"
        ))
        if temp is None:
            temp = max(18.0, min(35.0, self.temperature_c + random.uniform(-0.3, 0.3)))

        return dist_cm, l_val, s_val, temp

    def _loop(self):
        """Main autonomous loop."""
        while not self._stop_event.is_set():
            # 1. Get Data
            dist, light, soil, temp = self._read_sensors()

            with self.lock:
                self.distance = dist
                self.light_val = light
                self.soil_val = soil
                self.temperature_c = temp

            # 2. Apply Logic
            self._apply_logic(dist, light, soil)

            # 3. Wait
            time.sleep(0.1) # Update frequency - faster polling for serial data

    def _apply_logic(self, dist, light, soil):
        """Decides face and movement based on sensors."""
        
        # Logic 1: Missing Data
        if light is None or soil is None:
            self.current_face = FACES["sad"]
            self.stop_motors()
            return

        # Logic 2: It's Dark -> Sleep
        if light == 0:
            self.current_face = FACES["sleep"]
            self.stop_motors()
        
        # Logic 3: Dry Soil -> Tired & Slow
        elif soil < 30:
            self.current_face = FACES["tired"]
            if dist > 30:
                self.move_forward(0.6)
            else:
                self.rotate(0.8)
        
        # Logic 4: Happy & Active
        else:
            self.current_face = FACES["awake"]
            if dist > 30:
                self.move_forward(1.0)
            else:
                self.rotate(1.0)

    def get_state(self) -> RobotState:
        with self.lock:
            return RobotState(
                light_val=self.light_val,
                soil_val=self.soil_val,
                distance_cm=self.distance,
                current_face=self.current_face,
                motor_state=self.motor_state,
                temperature_c=self.temperature_c,
                gesture_label=self.gesture_label,
                gesture_mode=self.gesture_mode,
                gesture_message=self.gesture_message,
                gesture_detected_at=self.gesture_detected_at
            )

    def update_gesture(self, label: Optional[str], mode: Optional[str]):
        with self.lock:
            self.gesture_label = label
            self.gesture_mode = mode

            if label:
                target_mode = mode or "standby"
                self.gesture_message = f"Gesture {label} detected → engaging {target_mode}"
                self.gesture_detected_at = time.strftime("%H:%M:%S")
            else:
                self.gesture_message = "No gesture detected"
                self.gesture_detected_at = None

    # -------------------------------
    # NEW: SEND GESTURE TO STM32 HERE
    # -------------------------------
        if self.serial_conn and label:
            print("serialconn success")

    def close(self):
        self._stop_event.set()
        self._thread.join(timeout=1)
        self.stop_motors()
        if self.serial_conn:
            self.serial_conn.close()
        if not self.use_mock_hardware and self.distance_sensor:
            self.distance_sensor.close()
            self.motor_right.close()
            self.motor_left.close()


# --- 3. Web Server Setup ---

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

robot = RobotController()

@app.on_event("shutdown")
def shutdown_event():
    robot.close()

@app.get("/state", response_model=RobotState)
async def get_state():
    return robot.get_state()

@app.post("/gesture")
async def ingest_gesture(update: GestureUpdate):
    robot.update_gesture(update.gesture, update.mode)
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

if __name__ == "__main__":
    print("Starting Robot Server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
