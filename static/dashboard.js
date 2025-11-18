const faceEl = document.getElementById('face');
const timestampEl = document.getElementById('timestamp');
const lightValueEl = document.getElementById('light-value');
const lightStatusEl = document.getElementById('light-status');
const soilValueEl = document.getElementById('soil-value');
const soilStatusEl = document.getElementById('soil-status');
const distanceValueEl = document.getElementById('distance-value');
const distanceStatusEl = document.getElementById('distance-status');
const motorValueEl = document.getElementById('motor-value');
const motorStatusEl = document.getElementById('motor-status');

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

function updateMotor(motorState) {
    if (!motorState) {
        motorValueEl.textContent = 'Idle';
        motorStatusEl.textContent = 'Awaiting command';
        motorStatusEl.className = CLASS_IDLE;
        return;
    }

    motorValueEl.textContent = motorState;
    const normalized = motorState.toLowerCase();
    if (normalized.includes('stop')) {
        motorStatusEl.textContent = 'Stopped';
        motorStatusEl.className = CLASS_IDLE;
    } else if (normalized.includes('forward')) {
        motorStatusEl.textContent = 'Moving forward';
        motorStatusEl.className = CLASS_GOOD;
    } else {
        motorStatusEl.textContent = 'Adjusting position';
        motorStatusEl.className = CLASS_WARN;
    }
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
        motorValueEl.textContent = 'Offline';
        motorStatusEl.textContent = 'Connection lost';
        motorStatusEl.className = CLASS_BAD;
        return;
    }

    faceEl.textContent = data.current_face || '0 ___ 0';
    updateLight(data.light_val);
    updateSoil(data.soil_val);
    updateDistance(data.distance_cm);
    updateMotor(data.motor_state);
}

setInterval(updateDashboard, 1200);
updateDashboard();
