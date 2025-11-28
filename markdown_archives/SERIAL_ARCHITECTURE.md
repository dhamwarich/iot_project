# Serial Communication Architecture

## Problem Solved
Previously, both `app.py` and `gesture_detect.py` tried to open `/dev/ttyACM0` simultaneously, causing serial port conflicts and blocking sensor data flow.

## New Architecture

### Single Serial Connection (app.py)
- **app.py** has exclusive access to `/dev/ttyACM0`
- Continuously reads sensor data from STM32 (light, soil, distance)
- Writes gesture commands to STM32 when received via HTTP API
- Handles automatic reconnection on serial errors

### Gesture Detection (gesture_detect.py)
- Runs camera-based hand gesture detection
- Sends gesture commands to app.py via HTTP POST to `/gesture` endpoint
- **No direct serial connection** - prevents port conflicts

## Data Flow

```
STM32 ──serial──> app.py ──HTTP──> Dashboard (browser)
                    ↑
                    │ HTTP POST /gesture
                    │
              gesture_detect.py (camera)
                    
app.py ──serial──> STM32 (gesture commands)
```

## Running the System

### 1. Start the main app (must be first):
```bash
python app.py
```

### 2. Start gesture detection (in separate terminal):
```bash
python gesture_detect.py
```

### 3. Access dashboard:
```
http://localhost:8000
# or via ngrok for remote access
```

## Gesture Commands

| Gesture | Mode | STM32 Command |
|---------|------|---------------|
| Fist    | forward | '0' |
| One finger | spin | '1' |
| Open hand | wave | '2' |
| None | standby | '3' |

## Troubleshooting

### Dashboard not updating
- Check if `app.py` is running
- Look for `[SERIAL] Raw:` messages in app.py logs
- Verify STM32 is connected to `/dev/ttyACM0`

### Gesture commands not working
- Ensure `gesture_detect.py` is running
- Check for `[gesture_detect] Sent:` messages
- Verify `app.py` shows `[SERIAL] Sent command to STM32:`

### Serial port conflicts
- **Never run `screen /dev/ttyACM0` while app.py is running**
- Only one process can access the serial port at a time
- If stuck, restart app.py (it will auto-reconnect)
