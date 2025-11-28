# DHT11 Temperature & Humidity Sensor Setup (GPIO 17)

## Hardware Connection

### DHT11 Pinout (3-pin module)
```
DHT11 Sensor Module:
- VCC (+)     → RPI 5V (Pin 2 or 4) or 3.3V (Pin 1 or 17)
- GND (-)     → RPI GND (Pin 6, 9, 14, 20, 25, 30, 34, or 39)
- DATA (OUT)  → RPI GPIO 17 (Pin 11)
```

### Wiring Diagram
```
Raspberry Pi          DHT11 Module
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pin 2 (5V)      →     VCC (+)
Pin 6 (GND)     →     GND (-)
Pin 11 (GPIO17) →     DATA (OUT)
```

**Note:** Most DHT11 modules have a built-in pull-up resistor. If using a bare DHT11 sensor (4-pin), add a 10kΩ resistor between DATA and VCC.

## Software Setup on RPI

### 1. Install Required Libraries
```bash
# Update system
sudo apt-get update
sudo apt-get install -y python3-pip libgpiod2

# Install Adafruit libraries
pip install adafruit-circuitpython-dht
pip install adafruit-blinka
```

### 2. Test the Sensor
Create a test script:
```python
import time
import board
import adafruit_dht

# Initialize DHT11 on GPIO 17
dht_device = adafruit_dht.DHT11(board.D17)

try:
    while True:
        try:
            temperature = dht_device.temperature
            humidity = dht_device.humidity
            print(f"Temperature: {temperature:.1f}°C")
            print(f"Humidity: {humidity:.1f}%")
        except RuntimeError as e:
            # DHT sensors occasionally fail to read, this is normal
            print(f"Reading error: {e}")
        
        time.sleep(2.0)  # DHT11 requires 2 seconds between reads
        
except KeyboardInterrupt:
    print("Exiting...")
finally:
    dht_device.exit()
```

Save as `test_dht11.py` and run:
```bash
python test_dht11.py
```

Expected output:
```
Temperature: 25.0°C
Humidity: 60.0%
```

## Integration with app.py

The code now:
1. **Tries RPI DHT11 first** (most accurate, local sensor)
2. **Falls back to STM32 serial data** (if DHT11 unavailable)
3. **Uses mock data** (if both unavailable)

### Expected Startup Log
```bash
✓ DHT11 sensor initialized on GPIO 17
GPIO hardware initialized.
✓ Serial connected on /dev/ttyACM0 @ 115200 bps
```

### Important Notes

**DHT11 Reading Constraints:**
- Minimum 2 seconds between reads (enforced in code)
- Occasional read failures are normal (handled with try/except)
- Temperature range: 0-50°C (±2°C accuracy)
- Humidity range: 20-90% (±5% accuracy)

## Troubleshooting

### "Failed to open /dev/gpiomem"
```bash
sudo usermod -a -G gpio $USER
# Logout and login again
```

### "RuntimeError: A full buffer was not returned"
This is normal for DHT sensors. The code handles this automatically by:
- Throttling reads to 2+ seconds apart
- Catching RuntimeError exceptions
- Using previous/fallback values

### Sensor Not Responding
1. **Check wiring:**
   - VCC to 5V or 3.3V
   - GND to GND
   - DATA to GPIO 17 (physical pin 11)

2. **Verify GPIO:**
   ```bash
   gpio readall  # Check GPIO 17 is available
   ```

3. **Test with different GPIO:**
   If GPIO 17 doesn't work, try GPIO 4:
   ```python
   # In app.py line 137, change:
   self.dht_sensor = adafruit_dht.DHT11(board.D4)
   ```

### Permission Errors
```bash
sudo chmod 666 /dev/gpiomem
# Or run with sudo (not recommended for production)
```

## DHT11 vs DHT22

If you have a **DHT22** instead (blue sensor, more accurate):

Change line 137 in `app.py`:
```python
# From:
self.dht_sensor = adafruit_dht.DHT11(board.D17)

# To:
self.dht_sensor = adafruit_dht.DHT22(board.D17)
```

DHT22 specs:
- Temperature: -40 to 80°C (±0.5°C accuracy)
- Humidity: 0-100% (±2% accuracy)
- Same 2-second minimum read interval

## Bonus: Humidity Data

The DHT11 also provides humidity data. To use it in your dashboard, uncomment line 380 in `app.py`:
```python
humidity = self.dht_sensor.humidity
```

Then add humidity to the state model and dashboard display.
