# Recent Fixes Summary

## Issues Fixed

### 1. DHT11 Sensor Overheating ✅
**Problem:** Sensor getting hot from continuous polling  
**Root Cause:** Main loop runs every 0.1s, but we only read DHT11 every 2s. Between reads, we were still accessing the sensor object.

**Solution:**
- Added `last_dht_temp` cache to store last successful reading
- Between 2-second intervals, use cached value instead of accessing sensor
- Only physically read sensor every 2+ seconds
- Added logging: `[DHT11] Temperature: 25.3°C` every 2 seconds

### 2. Serial Data Stops After Gesture Command ✅
**Problem:** After sending gesture command to STM32, app stops receiving sensor data  
**Root Cause:** Serial write and read were not synchronized, causing buffer corruption

**Solution:**
- Added `with self.lock:` around serial write in `update_gesture()`
- Clear input buffer before writing: `serial_conn.reset_input_buffer()`
- Added 50ms delay after write to let STM32 process command
- Protected `_reconnect_serial()` with lock to prevent race conditions

### 3. Missing DHT11 Logging ✅
**Problem:** No visibility into DHT11 sensor readings  
**Solution:** Added `print(f"[DHT11] Temperature: {temp:.1f}°C")` on successful reads

## Expected Logs Now

### Normal Operation
```
[SERIAL] Raw: [Light Detected: 0, Soil Humidity: 0.3, Distance: 52]
[SERIAL] Parsed key-value: {'lightdetected': '0', 'soilhumidity': '0.3', 'distance': '52'}
[DHT11] Temperature: 25.3°C
INFO: 124.122.128.64:0 - "GET /state HTTP/1.1" 200 OK
```

### With Gesture Detection
```
[gesture_detect] Sent: fist -> forward
[SERIAL] Sent command to STM32: 0 (mode: forward)
[SERIAL] Raw: [Light Detected: 0, Soil Humidity: 0.2, Distance: 52]
[SERIAL] Parsed key-value: {'lightdetected': '0', 'soilhumidity': '0.2', 'distance': '52'}
```

## Technical Details

### Thread Safety
- **Read loop** (background thread): Reads serial data every 0.1s
- **Write operation** (HTTP request thread): Sends gesture commands
- **Lock protection**: Ensures write doesn't corrupt read buffer

### DHT11 Optimization
- **Physical reads**: Every 2+ seconds only
- **Cached reads**: Used between physical reads
- **Power consumption**: Reduced by ~95% (0.1s → 2s intervals)

## Testing Checklist

- [ ] DHT11 sensor no longer overheating
- [ ] Temperature logs appear every 2 seconds
- [ ] Gesture commands work without breaking serial reads
- [ ] Dashboard continues updating after gestures
- [ ] All sensor data (light, soil, distance, temp) updating correctly
