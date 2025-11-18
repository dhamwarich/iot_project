import serial
import time
import threading
import os
from gpiozero import Motor, DistanceSensor
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# --- 1. Robot Face States and Data Model ---

FACES = {
    "awake": "0 ___ 0",
    "sleep": "- ___ -",
    "tired": "? ___ ?",
    "sad": "T ___ T",
}

class RobotState(BaseModel):
    """Pydantic model for the API response data structure."""
    light_val: int | None
    soil_val: float | None
    distance_cm: float
    current_face: str
    motor_state: str

# --- 2. RobotController Class (Core Logic) ---

class RobotController:
    """Manages robot hardware and state."""
    def __init__(self, port="/dev/ttyACM0", baudrate=115200):
        # Serial connection (handle mock mode)
        try:
            self.serial_conn = serial.Serial(port, baudrate, timeout=0.1)
        except serial.SerialException as e:
            print(f"Warning: Could not open serial port {port}. Running in mock mode. Error: {e}")
            self.serial_conn = None
        
        # Hardware setup (handle mock mode)
        try:
            # GPIO pin numbers are hardcoded as in the original script
            self.distance_sensor = DistanceSensor(echo=23, trigger=24)
            self.motor_right = Motor(27, 22)
            self.motor_left = Motor(16, 20)
            self.hardware_initialized = True
        except Exception as e:
            print(f"Warning: Could not initialize gpiozero hardware. Running in mock mode. Error: {e}")
            self.hardware_initialized = False
            # Mock objects for safe execution when not on a Raspberry Pi
            class MockMotor:
                def forward(self, speed): pass
                def backward(self, speed): pass
                def stop(self): pass
            class MockDistanceSensor:
                @property
                def distance(self): return 0.5 # 50 cm mock distance

            self.motor_right = MockMotor()
            self.motor_left = MockMotor()
            self.distance_sensor = MockDistanceSensor()
        
        # State variables
        self.current_face = FACES["awake"]
        self.light_val = None
        self.soil_val = None
        self.distance = self.distance_sensor.distance * 100
        self.motor_state = "STOPPED"
        self.lock = threading.Lock() # For thread-safe state updates

        # Start background sensor reading thread
        self._stop_event = threading.Event()
        self._sensor_thread = threading.Thread(target=self._sensor_reader_loop, daemon=True)
        self._sensor_thread.start()

    # --- Motor & Face Methods (Same as original) ---

    def display_face(self, face):
        self.current_face = face

    def stop_motors(self):
        self.motor_right.stop()
        self.motor_left.stop()
        self.motor_state = "STOPPED"

    def move_forward(self, speed=1.0):
        self.motor_right.forward(speed)
        self.motor_left.forward(speed)
        self.motor_state = f"FORWARD ({speed:.1f})"

    def rotate(self, speed=1.0):
        self.motor_left.forward(speed)
        self.motor_right.backward(speed)
        self.motor_state = f"ROTATING ({speed:.1f})"

    # --- Sensor Reading & Control Loop ---

    def read_sensor_line(self):
        """Reads and parses data from the serial connection (STM32)."""
        if not self.serial_conn:
            # Mock data for testing without hardware
            return 1, 50.0 
            
        try:
            line = self.serial_conn.readline().decode("utf-8", errors="replace").strip()
            if not line: return None, None

            # Clean and parse the line (adapted from original logic)
            line = line.replace("[", "").replace("]", "")
            line = line.replace("Light Detected: ", "").replace("Soil Humidity: ", "")
            parts = line.split(",")
            
            if len(parts) == 2:
                light_val = int(parts[0].strip())
                soil_val = float(parts[1].strip())
                return light_val, soil_val
        except Exception as e:
            # print(f"[Parse Error] {e}")
            pass
        return None, None

    def _sensor_reader_loop(self):
        """Background thread loop to continuously read sensors and run control logic."""
        while not self._stop_event.is_set():
            light_val, soil_val = self.read_sensor_line()
            
            distance = self.distance_sensor.distance * 100 if self.hardware_initialized else 50.0

            with self.lock:
                self.light_val = light_val
                self.soil_val = soil_val
                self.distance = distance
            
            self.run_control_logic()

            time.sleep(0.1) # Loop pacing

    def run_control_logic(self):
        """Applies control logic based on sensor state."""
        with self.lock:
            light_val = self.light_val
            soil_val = self.soil_val
            distance = self.distance
        
        # --- Control Logic (Same as original script) ---
        if light_val is None or soil_val is None:
            self.display_face(FACES["sad"])
            self.stop_motors()
            return

        # Dark → stop
        if light_val == 0:
            self.display_face(FACES["sleep"])
            self.stop_motors()
        # Dry → move slower
        elif soil_val < 30:
            self.display_face(FACES["tired"])
            if distance > 30:
                self.move_forward(speed=0.6)
            else:
                self.rotate(speed=0.8)
        # Normal
        else:
            self.display_face(FACES["awake"])
            if distance > 30:
                self.move_forward(speed=1.0)
            else:
                self.rotate(speed=1.0)


    def get_state(self) -> RobotState:
        """Returns the current state of the robot for the API."""
        with self.lock:
            return RobotState(
                light_val=self.light_val,
                soil_val=self.soil_val,
                distance_cm=self.distance,
                current_face=self.current_face,
                motor_state=self.motor_state
            )

    def close(self):
        """Cleanup resources on shutdown."""
        self.stop_motors()
        self._stop_event.set()
        self._sensor_thread.join(timeout=1)
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()

# --- 3. FastAPI Application Setup ---

app = FastAPI()

# Global instance of the robot controller
try:
    ROBOT = RobotController()
except Exception as e:
    print(f"FATAL: Error initializing RobotController: {e}")
    # Handle critical error appropriately (e.g., raise or use a mock)

@app.on_event("shutdown")
def shutdown_event():
    """Ensure cleanup function runs when the server stops."""
    print("[FastAPI] Shutting down robot...")
    ROBOT.close()
    print("[FastAPI] Shutdown complete.")

# --- 4. API Endpoint ---

@app.get("/state", response_model=RobotState)
async def get_robot_state():
    """API endpoint to get the current sensor and motor state."""
    return ROBOT.get_state()

# --- 5. Frontend HTML Endpoint ---

@app.get("/", response_class=HTMLResponse)
async def serve_frontend(request: Request):
    """Serves the main HTML dashboard page."""
    
    # We embed the HTML/JS directly in the Python file for the single-file request
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Robot Dashboard</title>
    <style>
        body {{ font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #f4f4f9; }}
        .dashboard {{ background: #fff; padding: 30px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); width: 400px; }}
        h1 {{ text-align: center; color: #333; }}
        .face-display {{ font-size: 3em; text-align: center; margin: 20px 0; padding: 10px; border: 2px solid #ccc; border-radius: 5px; background-color: #e9e9e9; }}
        .sensor-item {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px dashed #ddd; }}
        .sensor-item:last-child {{ border-bottom: none; }}
        .label {{ font-weight: bold; color: #555; }}
        .value {{ color: #007bff; }}
        .status-good {{ color: green; }}
        .status-warn {{ color: orange; }}
        .status-bad {{ color: red; }}
    </style>
</head>
<body>

<div class="dashboard">
    <h1>🤖 Robot Status</h1>

    <div id="face-output" class="face-display">
        Waiting for data...
    </div>

    <div class="sensor-item">
        <span class="label">Light Sensor:</span>
        <span id="light-output" class="value">N/A</span>
    </div>

    <div class="sensor-item">
        <span class="label">Soil Humidity:</span>
        <span id="soil-output" class="value">N/A</span>
    </div>
    
    <div class="sensor-item">
        <span class="label">Distance (cm):</span>
        <span id="distance-output" class="value">N/A</span>
    </div>
    
    <div class="sensor-item">
        <span class="label">Motor State:</span>
        <span id="motor-output" class="value">N/A</span>
    </div>
</div>

<script>
    const API_URL = '/state';
    const lightOutput = document.getElementById('light-output');
    const soilOutput = document.getElementById('soil-output');
    const distanceOutput = document.getElementById('distance-output');
    const faceOutput = document.getElementById('face-output');
    const motorOutput = document.getElementById('motor-output');

    /**
     * Fetches robot state and updates the dashboard.
     */
    async function updateDashboard() {{
        try {{
            const response = await fetch(API_URL);
            const state = await response.json();

            // Update Sensor Values
            lightOutput.textContent = state.light_val !== null ? (state.light_val === 1 ? '💡 Detected' : '🌑 Dark') : 'N/A';
            lightOutput.className = state.light_val === 1 ? 'value status-good' : 'value status-bad';
            
            soilOutput.textContent = state.soil_val !== null ? `${{state.soil_val.toFixed(1)}} %` : 'N/A';
            if (state.soil_val !== null) {{
                soilOutput.className = state.soil_val >= 50 ? 'value status-good' : (state.soil_val >= 30 ? 'value status-warn' : 'value status-bad');
            }} else {{
                soilOutput.className = 'value';
            }}
            
            distanceOutput.textContent = state.distance_cm.toFixed(1) + ' cm';
            distanceOutput.className = state.distance_cm > 30 ? 'value status-good' : 'value status-warn';

            // Update Face and Motor
            faceOutput.textContent = state.current_face;
            motorOutput.textContent = state.motor_state;

        }} catch (error) {{
            console.error('Failed to fetch robot state:', error);
            lightOutput.textContent = 'ERROR';
            soilOutput.textContent = 'ERROR';
            distanceOutput.textContent = 'ERROR';
            faceOutput.textContent = 'X ___ X';
            motorOutput.textContent = 'UNKNOWN';
        }}
    }}

    // Update the dashboard every 1000 milliseconds (1 second)
    setInterval(updateDashboard, 1000);

    // Initial update
    updateDashboard();

</script>

</body>
</html>
    """
    return HTMLResponse(content=html_content)

# --- 6. Execution Block (Standard Python Run) ---

if __name__ == "__main__":
    # Import uvicorn locally to allow running the file directly
    try:
        import uvicorn
        print("Starting FastAPI server. Access the dashboard at http://127.0.0.1:8000/")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except ImportError:
        print("Uvicorn not installed. Please install it with 'pip install uvicorn'.")
