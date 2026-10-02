const endpointInput = document.querySelector("#endpointInput");
const rateInput = document.querySelector("#rateInput");
const sensorToggle = document.querySelector("#sensorToggle");
const permissionButton = document.querySelector("#permissionButton");
const startButton = document.querySelector("#startButton");
const stopButton = document.querySelector("#stopButton");
const statusPill = document.querySelector("#statusPill");
const sequenceValue = document.querySelector("#sequenceValue");
const modeValue = document.querySelector("#modeValue");
const quatValue = document.querySelector("#quatValue");
const gyroValue = document.querySelector("#gyroValue");
const eventLog = document.querySelector("#eventLog");

let sequence = 0;
let timer = null;
let latestOrientation = null;
let previousSample = null;

function log(message) {
  const time = new Date().toLocaleTimeString();
  eventLog.textContent = `[${time}] ${message}\n${eventLog.textContent}`.slice(0, 5000);
}

function setRunning(running) {
  startButton.disabled = running;
  stopButton.disabled = !running;
  statusPill.textContent = running ? "running" : "stopped";
  statusPill.classList.toggle("running", running);
}

function degToRad(value) {
  return (value || 0) * Math.PI / 180;
}

function eulerZxyToQuat(alphaDeg, betaDeg, gammaDeg) {
  const yaw = degToRad(alphaDeg);
  const pitch = degToRad(betaDeg);
  const roll = degToRad(gammaDeg);

  const cy = Math.cos(yaw * 0.5);
  const sy = Math.sin(yaw * 0.5);
  const cp = Math.cos(pitch * 0.5);
  const sp = Math.sin(pitch * 0.5);
  const cr = Math.cos(roll * 0.5);
  const sr = Math.sin(roll * 0.5);

  return normalizeQuat([
    cy * cp * cr + sy * sp * sr,
    cy * cp * sr - sy * sp * cr,
    sy * cp * sr + cy * sp * cr,
    sy * cp * cr - cy * sp * sr,
  ]);
}

function normalizeQuat(q) {
  const n = Math.hypot(q[0], q[1], q[2], q[3]) || 1;
  return q.map((v) => v / n);
}

function simulatedQuat(t) {
  const yaw = 0.55 * Math.sin(t * 0.8);
  const pitch = 0.25 * Math.sin(t * 1.3);
  const roll = 0.18 * Math.cos(t * 0.9);
  return eulerZxyToQuat(yaw * 180 / Math.PI, pitch * 180 / Math.PI, roll * 180 / Math.PI);
}

function quatDiffRate(prev, next, dt) {
  if (!prev || dt <= 0) {
    return [0, 0, 0];
  }
  return [
    (next[1] - prev[1]) * 2 / dt,
    (next[2] - prev[2]) * 2 / dt,
    (next[3] - prev[3]) * 2 / dt,
  ];
}

function fixedVector(values, digits = 4) {
  return `[${values.map((value) => Number(value).toFixed(digits)).join(", ")}]`;
}

async function postMessage(message) {
  const response = await fetch(endpointInput.value, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(message),
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
}

async function sendTick() {
  const now = performance.now() / 1000;
  const usingSensors = sensorToggle.checked && latestOrientation;
  const q = usingSensors
    ? eulerZxyToQuat(latestOrientation.alpha, latestOrientation.beta, latestOrientation.gamma)
    : simulatedQuat(now);
  const dt = previousSample ? now - previousSample.time : 0;
  const gyro = quatDiffRate(previousSample?.q, q, dt);

  const reference = {
    schema_version: "1.0",
    message_type: "REFERENCE_STATE",
    source: "WEB",
    device_time_s: now,
    sequence: sequence++,
    payload: {
      state_source: usingSensors ? "WebDeviceOrientation" : "WebSimulator",
      position_available: false,
      velocity_available: false,
      position_m: [0, 0, 0],
      velocity_mps: [0, 0, 0],
      quaternion_wxyz: q,
      tracking_state: usingSensors ? "browser_sensor" : "simulated",
    },
  };

  const raw = {
    schema_version: "1.0",
    message_type: "RAW_SENSOR",
    source: "WEB",
    device_time_s: now,
    sequence: sequence++,
    payload: {
      gyro_radps: gyro,
      accel_mps2: [0, 0, 9.80665],
    },
  };

  await postMessage(reference);
  await postMessage(raw);
  previousSample = { time: now, q };
  sequenceValue.textContent = String(sequence);
  modeValue.textContent = reference.payload.state_source;
  quatValue.textContent = fixedVector(q);
  gyroValue.textContent = fixedVector(gyro);
}

async function requestSensorPermission() {
  const maybeOrientation = window.DeviceOrientationEvent;
  if (maybeOrientation && typeof maybeOrientation.requestPermission === "function") {
    const permission = await maybeOrientation.requestPermission();
    log(`Sensorfreigabe: ${permission}`);
  } else {
    log("Keine explizite Sensorfreigabe noetig oder nicht verfuegbar.");
  }
}

window.addEventListener("deviceorientation", (event) => {
  latestOrientation = {
    alpha: event.alpha || 0,
    beta: event.beta || 0,
    gamma: event.gamma || 0,
  };
});

permissionButton.addEventListener("click", async () => {
  try {
    await requestSensorPermission();
  } catch (error) {
    log(`Sensorfreigabe fehlgeschlagen: ${error.message}`);
  }
});

startButton.addEventListener("click", () => {
  if (timer) {
    return;
  }
  sequence = 0;
  previousSample = null;
  const periodMs = Math.max(16, Math.round(1000 / Number(rateInput.value || 30)));
  timer = window.setInterval(() => {
    sendTick().catch((error) => {
      log(`Senden fehlgeschlagen: ${error.message}`);
      stopButton.click();
    });
  }, periodMs);
  setRunning(true);
  log(`Stream gestartet mit ${rateInput.value} Hz.`);
});

stopButton.addEventListener("click", () => {
  if (timer) {
    window.clearInterval(timer);
    timer = null;
  }
  setRunning(false);
  log("Stream gestoppt.");
});
