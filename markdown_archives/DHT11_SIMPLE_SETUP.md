# DHT11 Setup - Simple Method (No libgpiod)

## Why This Change?

Switched from `adafruit-circuitpython-dht` to `Adafruit_DHT` because:
- ❌ Old library required `libgpiod` (system dependency)
- ✅ New library uses simpler GPIO access
- ✅ Just `pip install` - no system packages needed
- ✅ More stable and battle-tested

## Installation on RPI

```bash
# In your project directory
pip install -r requirements.txt
```

That's it! No `sudo apt-get` needed.

## Wiring (Same as Before)

```
DHT11 Module → Raspberry Pi
━━━━━━━━━━━━━━━━━━━━━━━━━━━
VCC (+)      → Pin 2 (5V) or Pin 1 (3.3V)
GND (-)      → Pin 6 (GND)
DATA (OUT)   → Pin 11 (GPIO 17)
```

## Expected Output

```bash
✓ DHT11 sensor ready on GPIO 17
GPIO hardware initialized.
✓ Serial connected on /dev/ttyACM0 @ 115200 bps

[DHT11] Temperature: 25.3°C, Humidity: 60.0%
[SERIAL] Raw: [Light Detected: 0, Soil Humidity: 0.3, Distance: 52]
```

## Key Differences

### Old Library (adafruit-circuitpython-dht)
```python
import adafruit_dht
import board
sensor = adafruit_dht.DHT11(board.D17)
temp = sensor.temperature
```
- Required: `libgpiod2`, `adafruit-blinka`
- More modern but complex dependencies

### New Library (Adafruit_DHT)
```python
import Adafruit_DHT
humidity, temp = Adafruit_DHT.read_retry(Adafruit_DHT.DHT11, 17)
```
- Required: Just `Adafruit_DHT`
- Simpler, more reliable
- Built-in retry logic

## Bonus: Humidity Data

The new library also reads humidity! Check the logs:
```
[DHT11] Temperature: 25.3°C, Humidity: 60.0%
```

## Troubleshooting

### "No module named 'Adafruit_DHT'"
```bash
pip install Adafruit_DHT
```

### Still getting timeout errors
1. Check wiring (especially DATA pin to GPIO 17)
2. Try with sudo once to test: `sudo python app.py`
3. If sudo works, add user to gpio group:
   ```bash
   sudo usermod -a -G gpio $USER
   # Logout and login
   ```

### Sensor reads None
- Normal occasionally - the library retries 3 times automatically
- Uses cached value between reads
- If persistent, check wiring or try different GPIO pin
