import serial
import threading
import time
import ast
# import RPi.GPIO as GPIO
from gpiozero import Motor, DistanceSensor
from RPLCD.i2c import CharLCD



class SensorReader:
    def __init__(self, port="/dev/ttyACM0", baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.running = False
        self.latest_values = []

    def start(self):
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            self.running = True
            threading.Thread(target=self._read_loop, daemon=True).start()
            print("SensorReader started.")
        except serial.SerialException as e:
            print(f"[SensorReader] Serial Error: {e}")

    def stop(self):
        self.running = False
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        print("SensorReader stopped.")

    def _read_loop(self):
        while self.running and self.serial_conn and self.serial_conn.is_open:
            try:
                line = self.serial_conn.readline().decode("utf-8", errors="replace").strip()
                if line.startswith("[") and line.endswith("]"):
                    try:
                        values = ast.literal_eval(line)
                        if isinstance(values, list):
                            self.latest_values = values
                            print(f"[SensorReader] Received: {values}")
                    except Exception as e:
                        print(f"[SensorReader] Parse error: {e}")
            except Exception as e:
                print(f"[SensorReader] Read error: {e}")
            
            line = self.serial_conn.readline().decode("utf-8", errors="replace").strip()
            self.latest_values = line
            time.sleep(0.1)

    def get_latest_values(self):
        return self.latest_values
        
     

# === Example Main Logic ===
def main():
	lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1, cols=16, rows=2, dotsize=8)
	lcd.clear()
	sensor_reader = SensorReader(port="/dev/ttyACM0", baudrate=115200)
	distanceSensor = DistanceSensor(echo=23, trigger=24)
	motor_right = Motor(22, 27)
	motor_left = Motor(16, 20)
	try:
		sensor_reader.start()
		while True:
			values = sensor_reader.get_latest_values()
			distance = distanceSensor.distance * 100
			light, soil, water = values
			print(f"from stm32: {values}, distance: {distance}")
			if distance < 25:
				# motor_right.forward()
				# motor_left.forward()
				pass
			else:
				# motor_right.stop()
				# motor_left.stop()
				pass
				
			if light == 0:
				lcd.write_string('sleep')
				
			time.sleep(0.2)
			
	except KeyboardInterrupt:
		print("\n[Main] Interrupted by user.")
	finally:
		print("[Main] Shutting down...")
		sensor_reader.stop()


if __name__ == "__main__":
    main()
