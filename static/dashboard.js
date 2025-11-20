const faceEl = document.getElementById('face');
const timestampEl = document.getElementById('timestamp');
const lightValueEl = document.getElementById('light-value');
const lightStatusEl = document.getElementById('light-status');
const soilValueEl = document.getElementById('soil-value');
const soilStatusEl = document.getElementById('soil-status');
const distanceValueEl = document.getElementById('distance-value');
const distanceStatusEl = document.getElementById('distance-status');
const temperatureValueEl = document.getElementById('temperature-value');
const temperatureStatusEl = document.getElementById('temperature-status');
const gesturePanelEl = document.getElementById('gesture-panel');
const gestureTimestampEl = document.getElementById('gesture-timestamp');
const gestureLabelEl = document.getElementById('gesture-label');
const gestureModeEl = document.getElementById('gesture-mode');
const gestureMessageEl = document.getElementById('gesture-message');

const CLASS_GOOD = 'metric__status status-good';
const CLASS_WARN = 'metric__status status-warn';
const CLASS_BAD = 'metric__status status-bad';
const CLASS_IDLE = 'metric__status status-idle';

async function fetchState() {
    try {
        const res = await fetch('/state');
        if (!res.ok) throw new Error('Network response not ok');
        return await res.json();
    } catch (err) {
        console.error('fetchState error', err);
        return null;
    }
}

function formatTime(date) {
    return date.toLocaleTimeString([], { hour12: false });
}

function updateLight(lightVal) {
    if (lightVal === null || lightVal === undefined) {
        lightValueEl.textContent = 'Unknown';
        lightStatusEl.textContent = 'No data';
        lightStatusEl.className = CLASS_IDLE;
        return;
    }

    const isBright = lightVal === 1;
    lightValueEl.textContent = isBright ? 'Bright' : 'Dark';
    lightStatusEl.textContent = isBright ? '🌤️ Awake' : '🌙 Sleeping';
    lightStatusEl.className = isBright ? CLASS_GOOD : CLASS_WARN;
}

function updateSoil(soilVal) {
    if (soilVal === null || soilVal === undefined) {
        soilValueEl.textContent = 'N/A';
        soilStatusEl.textContent = 'No data';
        soilStatusEl.className = CLASS_IDLE;
        return;
    }

    soilValueEl.textContent = `${soilVal.toFixed(1)} %`;
    if (soilVal >= 50) {
        soilStatusEl.textContent = 'Hydrated';
        soilStatusEl.className = CLASS_GOOD;
    } else if (soilVal >= 30) {
        soilStatusEl.textContent = 'Monitor soon';
        soilStatusEl.className = CLASS_WARN;
    } else {
        soilStatusEl.textContent = 'Needs water';
        soilStatusEl.className = CLASS_BAD;
    }
}

function updateDistance(dist) {
    if (typeof dist !== 'number') {
        distanceValueEl.textContent = '-- cm';
        distanceStatusEl.textContent = 'No data';
        distanceStatusEl.className = CLASS_IDLE;
        return;
    }

    distanceValueEl.textContent = `${dist.toFixed(1)} cm`;
    if (dist > 40) {
        distanceStatusEl.textContent = 'Clear path';
        distanceStatusEl.className = CLASS_GOOD;
    } else if (dist > 20) {
        distanceStatusEl.textContent = 'Obstacle nearby';
        distanceStatusEl.className = CLASS_WARN;
    } else {
        distanceStatusEl.textContent = 'Obstacle close';
        distanceStatusEl.className = CLASS_BAD;
    }
}

function updateTemperature(temp) {
    if (typeof temp !== 'number') {
        temperatureValueEl.textContent = '-- °C';
        temperatureStatusEl.textContent = 'No data';
        temperatureStatusEl.className = CLASS_IDLE;
        return;
    }

    temperatureValueEl.textContent = `${temp.toFixed(1)} °C`;
    if (temp < 20) {
        temperatureStatusEl.textContent = 'Cool zone';
        temperatureStatusEl.className = CLASS_WARN;
    } else if (temp <= 28) {
        temperatureStatusEl.textContent = 'Comfortable';
        temperatureStatusEl.className = CLASS_GOOD;
    } else if (temp <= 32) {
        temperatureStatusEl.textContent = 'Warm';
        temperatureStatusEl.className = CLASS_WARN;
    } else {
        temperatureStatusEl.textContent = 'Hot';
        temperatureStatusEl.className = CLASS_BAD;
    }
}

function updateGesture(gestureData) {
    if (!gestureData) {
        gesturePanelEl.classList.remove('gesture--active');
        gestureTimestampEl.textContent = '--:--:--';
        gestureLabelEl.textContent = 'No gesture';
        gestureModeEl.textContent = 'Mode: standby';
        gestureMessageEl.textContent = 'No gesture detected';
        return;
    }

    const { gesture_label, gesture_mode, gesture_message, gesture_detected_at } = gestureData;
    const active = Boolean(gesture_label);
    gesturePanelEl.classList.toggle('gesture--active', active);
    gestureTimestampEl.textContent = gesture_detected_at || '--:--:--';
    gestureLabelEl.textContent = gesture_label ? gesture_label.toUpperCase() : 'No gesture';
    gestureModeEl.textContent = `Mode: ${gesture_mode || 'standby'}`;
    gestureMessageEl.textContent = gesture_message || 'No gesture detected';
}

async function updateDashboard() {
    const data = await fetchState();
    const now = new Date();
    timestampEl.textContent = formatTime(now);

    if (!data) {
        faceEl.textContent = 'X ___ X';
        updateLight(null);
        updateSoil(null);
        updateDistance(null);
        updateTemperature(null);
        updateGesture(null);
        return;
    }

    faceEl.textContent = data.current_face || '0 ___ 0';
    updateLight(data.light_val);
    updateSoil(data.soil_val);
    updateDistance(data.distance_cm);
    updateTemperature(data.temperature_c);
    updateGesture({
        gesture_label: data.gesture_label,
        gesture_mode: data.gesture_mode,
        gesture_message: data.gesture_message,
        gesture_detected_at: data.gesture_detected_at
    });
}

setInterval(updateDashboard, 1200);
updateDashboard();
