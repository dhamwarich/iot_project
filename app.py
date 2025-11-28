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

# Temperature & Humidity sensor (DHT11)
try:
    import adafruit_dht
    import board
    DHT_SENSOR_AVAILABLE = True
except ImportError:
    print("Adafruit DHT library not found. Install with: pip install adafruit-circuitpython-dht")
    DHT_SENSOR_AVAILABLE = False
    adafruit_dht = board = None

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
        self.serial_port = port
        self.serial_baudrate = baudrate
        self.serial_error_count = 0
        self.last_reconnect_attempt = 0
        self.motor_right = None
        self.motor_left = None
        self.distance_sensor = None
        self.dht_sensor = None
        self.last_dht_read = 0  # Throttle DHT11 reads (min 2 sec between reads)
        self.last_dht_temp = None  # Cache last successful DHT11 reading
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
        
        # Temperature & Humidity sensor setup (DHT11 on GPIO 17)
        if DHT_SENSOR_AVAILABLE and adafruit_dht and board:
            try:
                self.dht_sensor = adafruit_dht.DHT11(board.D17)
                print("✓ DHT11 sensor initialized on GPIO 17")
            except Exception as exc:
                print(f"DHT11 sensor initialization failed ({exc}). Using serial/mock data.")
                self.dht_sensor = None
        else:
            print("DHT11 library not available. Using serial/mock data.")

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
                # Try to open with exclusive access
                conn = serial.Serial(candidate, baudrate, timeout=0.5, exclusive=True)
                time.sleep(0.2)  # Allow connection to stabilize
                conn.reset_input_buffer()
                conn.reset_output_buffer()
                print(f"✓ Serial connected on {candidate} @ {baudrate} bps")
                return conn
            except serial.SerialException as exc:
                # Port might be locked by screen or another process
                if "Resource busy" in str(exc) or "Permission denied" in str(exc):
                    print(f"✗ Serial port {candidate} is locked by another process (screen?). Close it first.")
                else:
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

    def _reconnect_serial(self):
        """Attempt to reconnect to serial port after disruption."""
        current_time = time.time()
        # Only try reconnecting once every 5 seconds
        if current_time - self.last_reconnect_attempt < 5:
            return False
        
        self.last_reconnect_attempt = current_time
        print("[SERIAL] Attempting to reconnect...")
        
        with self.lock:  # Protect serial connection changes
            # Close existing connection if any
            if self.serial_conn:
                try:
                    self.serial_conn.close()
                except:
                    pass
                self.serial_conn = None
            
            # Try to reconnect
            new_conn = self._init_serial_connection(self.serial_port, self.serial_baudrate)
            if new_conn:
                self.serial_conn = new_conn
                self.serial_error_count = 0
                print("[SERIAL] Reconnection successful!")
                return True
        return False

    def _read_serial_packet(self):
        if not self.serial_conn:
            # Try to reconnect if we don't have a connection
            self._reconnect_serial()
            return {}

        try:
            # Read line with timeout (set in serial connection)
            raw = self.serial_conn.readline().decode("utf-8", errors="replace").strip()
            if not raw:
                return {}  # Timeout or empty line

            # Debug: Print raw data (comment out after testing)
            print(f"[SERIAL] Raw: {raw}")
            
            # Detect garbage/corrupted data (single char or very short)
            if len(raw) < 5 or not any(c in raw for c in [':', '[', '{']):
                self.serial_error_count += 1
                print(f"[SERIAL] Warning: Received corrupted data (error count: {self.serial_error_count})")
                if self.serial_error_count >= 3:
                    print("[SERIAL] Too many errors, triggering reconnection...")
                    self._reconnect_serial()
                return {}

            # Reset error count on successful read
            self.serial_error_count = 0

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
                # Normalize key by removing spaces and converting to lowercase
                normalized_key = key.strip().lower().replace(" ", "")
                packet[normalized_key] = value.strip()
            
            if packet:
                print(f"[SERIAL] Parsed key-value: {packet}")
            else:
                # Empty packet might indicate corruption
                self.serial_error_count += 1
            return packet
        except (serial.SerialException, OSError) as e:
            print(f"[SERIAL] Connection error: {e}")
            self._reconnect_serial()
            return {}
        except Exception as e:
            print(f"[SERIAL] Error reading: {e}")
            self.serial_error_count += 1
            if self.serial_error_count >= 5:
                self._reconnect_serial()
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
            "light", "light_val", "lightdetected", "lightval"
        ), as_int=True)
        s_val = self._extract_serial_number(packet, (
            "soil", "soil_val", "soilhumidity", "soilval"
        ))
        
        # Convert soil from 0-1 range to 0-100 percentage if needed
        if s_val is not None and s_val <= 1.0:
            s_val = s_val * 100.0

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

        # Temperature (priority: RPI DHT11 > serial > mock)
        temp = None
        
        # Try RPI DHT11 sensor first (throttled to avoid read errors and overheating)
        if self.dht_sensor:
            current_time = time.time()
            # DHT11 requires minimum 2 seconds between reads
            if current_time - self.last_dht_read >= 2.0:
                try:
                    temp = self.dht_sensor.temperature
                    # humidity = self.dht_sensor.humidity  # Available if needed
                    self.last_dht_read = current_time
                    self.last_dht_temp = temp  # Cache successful reading
                    print(f"[DHT11] Temperature: {temp:.1f}°C")
                except RuntimeError as e:
                    # DHT sensors can occasionally fail to read, this is normal
                    # Use cached value if available
                    temp = self.last_dht_temp
                except Exception as e:
                    print(f"[DHT11] Error reading sensor: {e}")
                    temp = self.last_dht_temp
            else:
                # Use cached value between reads to avoid polling sensor
                temp = self.last_dht_temp
        
        # Fallback to serial data from STM32
        if temp is None:
            temp = self._extract_serial_number(packet, (
                "temperature", "temperature_c", "temp"
            ))
        
        # Final fallback to mock data
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
        # Mode mapping for STM32
        MODE_MAP = {
            "forward": '0',
            "spin": '1',
            "wave": '2',
            None: '3'
        }
        
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
        
        # Send mode command to STM32 via serial (with lock to prevent read corruption)
        if self.serial_conn and mode in MODE_MAP:
            with self.lock:  # CRITICAL: Synchronize with read loop
                try:
                    command = MODE_MAP[mode]
                    # Clear any pending input before writing to prevent buffer corruption
                    if self.serial_conn.in_waiting > 0:
                        self.serial_conn.reset_input_buffer()
                    
                    self.serial_conn.write(command.encode('utf-8'))
                    self.serial_conn.flush()
                    print(f"[SERIAL] Sent command to STM32: {command} (mode: {mode})")
                    
                    # Small delay to let STM32 process command before next read
                    time.sleep(0.05)
                except Exception as e:
                    print(f"[SERIAL] Error sending command to STM32: {e}")
                    # Don't trigger reconnection for write errors, only read errors

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
