import time
import threading
import random
from typing import Optional

# --- FASTAPI & SERVER IMPORTS ---
try:
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print("CRITICAL ERROR: Missing web libraries.")
    print("Please run: pip install fastapi uvicorn")
    exit(1)

# --- HARDWARE IMPORTS (With Fallback) ---
try:
    import serial
    from gpiozero import Motor, DistanceSensor
    HARDWARE_AVAILABLE = True
except ImportError:
    print("Hardware libraries (gpiozero/pyserial) not found. Running in MOCK MODE.")
    HARDWARE_AVAILABLE = False
    serial = None  # Placeholder

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

# --- 2. Robot Controller ---

class RobotController:
    def __init__(self, port="/dev/ttyACM0", baudrate=115200):
        self.lock = threading.Lock()
        self._stop_event = threading.Event()
        
        # State initialization
        self.current_face = FACES["awake"]
        self.light_val = 1
        self.soil_val = 50.0
        self.distance = 0.0
        self.motor_state = "STOPPED"

        # --- Hardware Setup ---
        self.serial_conn = None
        self.motor_right = None
        self.motor_left = None
        self.distance_sensor = None
        self.use_mock_hardware = not HARDWARE_AVAILABLE

        if HARDWARE_AVAILABLE:
            try:
                # Attempt Serial Connection
                try:
                    self.serial_conn = serial.Serial(port, baudrate, timeout=0.1)
                    print(f"Serial connected on {port}")
                except serial.SerialException:
                    print(f"Serial port {port} not found. Using Mock Serial data.")
                    self.serial_conn = None

                # Attempt GPIO Setup
                # Using specific pins from your snippet
                self.distance_sensor = DistanceSensor(echo=23, trigger=24)
                self.motor_right = Motor(forward=27, backward=22)
                self.motor_left = Motor(forward=16, backward=20)
                print("GPIO Hardware Initialized.")
                
            except Exception as e:
                print(f"Hardware initialization failed ({e}). Switching to Mock Mode.")
                self.use_mock_hardware = True

        # If we are mocking, we don't need real objects, just logic
        if self.use_mock_hardware:
            print("--- RUNNING IN MOCK MODE ---")

        # Start background thread
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

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

    def _read_sensors(self):
        """Reads real hardware or generates mock data."""
        
        # 1. Distance
        if not self.use_mock_hardware and self.distance_sensor:
            # gpiozero returns meters, convert to cm
            dist_cm = self.distance_sensor.distance * 100
        else:
            # Mock: Randomly fluctuate distance
            dist_cm = random.uniform(10, 100)

        # 2. Serial (Light/Soil)
        l_val, s_val = self.light_val, self.soil_val

        if self.serial_conn:
            try:
                line = self.serial_conn.readline().decode("utf-8", errors="replace").strip()
                if line:
                    # Parse: "[Light Detected: 1, Soil Humidity: 45.2]"
                    line = line.replace("[", "").replace("]", "")
                    line = line.replace("Light Detected: ", "").replace("Soil Humidity: ", "")
                    parts = line.split(",")
                    if len(parts) == 2:
                        l_val = int(parts[0].strip())
                        s_val = float(parts[1].strip())
            except Exception:
                pass # Keep last known values on error
        elif self.use_mock_hardware or self.serial_conn is None:
            # Mock: Randomly toggle light and fluctuate soil
            if random.random() > 0.95: # 5% chance to flip light
                l_val = 1 if l_val == 0 else 0
            
            # Jitter soil slightly
            change = random.uniform(-2, 2)
            s_val = max(0, min(100, s_val + change))

        return dist_cm, l_val, s_val

    def _loop(self):
        """Main autonomous loop."""
        while not self._stop_event.is_set():
            # 1. Get Data
            dist, light, soil = self._read_sensors()

            with self.lock:
                self.distance = dist
                self.light_val = light
                self.soil_val = soil

            # 2. Apply Logic
            self._apply_logic(dist, light, soil)

            # 3. Wait
            time.sleep(0.5) # Update frequency

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
                motor_state=self.motor_state
            )

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
robot = RobotController()

@app.on_event("shutdown")
def shutdown_event():
    robot.close()

@app.get("/state", response_model=RobotState)
async def get_state():
    return robot.get_state()

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Robot Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: 'Segoe UI', sans-serif; background: #f0f2f5; display: flex; justify-content: center; padding-top: 50px; }
            .card { background: white; padding: 2rem; border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); width: 350px; text-align: center; }
            .face { font-size: 4rem; font-family: monospace; margin: 1rem 0; background: #eee; padding: 1rem; border-radius: 10px; }
            .stat { display: flex; justify-content: space-between; padding: 0.8rem 0; border-bottom: 1px solid #eee; }
            .stat:last-child { border-bottom: none; }
            .val { font-weight: bold; color: #007bff; }
            .badge { padding: 4px 8px; border-radius: 4px; font-size: 0.9rem; color: white; }
            .bg-green { background: #28a745; }
            .bg-red { background: #dc3545; }
            .bg-grey { background: #6c757d; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>🤖 Plant Robot</h2>
            <div id="face" class="face">...</div>
            
            <div class="stat">
                <span>Light</span>
                <span id="light" class="badge bg-grey">...</span>
            </div>
            <div class="stat">
                <span>Soil Moisture</span>
                <span id="soil" class="val">...</span>
            </div>
            <div class="stat">
                <span>Distance</span>
                <span id="dist" class="val">...</span>
            </div>
            <div class="stat">
                <span>Motor</span>
                <span id="motor" class="val">...</span>
            </div>
        </div>

        <script>
            async function update() {
                try {
                    const res = await fetch('/state');
                    const data = await res.json();
                    
                    document.getElementById('face').innerText = data.current_face;
                    document.getElementById('soil').innerText = data.soil_val.toFixed(1) + '%';
                    document.getElementById('dist').innerText = data.distance_cm.toFixed(1) + ' cm';
                    document.getElementById('motor').innerText = data.motor_state;
                    
                    const lightEl = document.getElementById('light');
                    if(data.light_val === 1) {
                        lightEl.innerText = "BRIGHT";
                        lightEl.className = "badge bg-green";
                    } else {
                        lightEl.innerText = "DARK";
                        lightEl.className = "badge bg-red";
                    }
                } catch(e) { console.log(e); }
            }
            setInterval(update, 1000);
            update();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html)

if __name__ == "__main__":
    print("Starting Robot Server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
