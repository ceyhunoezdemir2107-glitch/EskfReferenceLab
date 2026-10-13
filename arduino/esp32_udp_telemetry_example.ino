// ESP32 UDP telemetry example for ESKF Reference Lab.
//
// Sends newline-free JSON packets over UDP to the Python logger:
//   python -m eskf_ref log --udp-host 0.0.0.0 --udp-port 5555 --out ..\logs\arduino_live.jsonl
//
// Replace the placeholder readEskfState/readRawImu functions with your real
// estimator and sensor outputs. Keep packets below the network MTU; one compact
// JSON object per UDP packet is intentional for live monitoring.

#include <FS.h>
#include <LittleFS.h>
#include <SD.h>
#include <SPI.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <math.h>

// Local blackbox logging. Prefer SD for flight tests. Switch to LittleFS for
// short bench tests without an SD card.
#define ENABLE_LOCAL_LOG 1
#define USE_SD_LOG 1
#define USE_LITTLEFS_LOG 0

// Compact long-range telemetry. UDP is useful for bench/WLAN tests. Serial2 is
// useful for transparent serial radios or a LoRa/telemetry modem.
#define ENABLE_TELEMETRY_SUMMARY 1
#define TELEMETRY_SUMMARY_TO_UDP 1
#define TELEMETRY_SUMMARY_TO_RADIO_SERIAL 0

const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

IPAddress PC_IP(192, 168, 0, 112);
const uint16_t PC_UDP_PORT = 5555;
const uint16_t LOCAL_UDP_PORT = 5556;
const int SD_CS_PIN = 5;
const uint32_t RADIO_SERIAL_BAUD = 57600;
const int RADIO_RX_PIN = 16;
const int RADIO_TX_PIN = 17;

const uint32_t TELEMETRY_SUMMARY_PERIOD_MS = 200; // 5 Hz
const uint32_t ESTIMATOR_PERIOD_MS = 20;   // 50 Hz
const uint32_t RAW_IMU_PERIOD_MS = 10;     // 100 Hz
const uint32_t DIAGNOSTIC_PERIOD_MS = 1000;
const uint32_t LOCAL_LOG_FLUSH_PERIOD_MS = 1000;

WiFiUDP udp;
uint32_t sequenceNumber = 0;
uint32_t lastTelemetrySummaryMs = 0;
uint32_t lastEstimatorMs = 0;
uint32_t lastRawImuMs = 0;
uint32_t lastDiagnosticMs = 0;
uint32_t lastLocalLogFlushMs = 0;
uint32_t localLogLinesSinceFlush = 0;
uint32_t localLogWriteErrors = 0;
fs::FS* localLogFs = nullptr;
File localLog;
char localLogPath[40] = "";
String serialCommand;

struct EskfState {
  float p[3];
  float v[3];
  float q[4];  // w, x, y, z
  float ba[3];
  float bg[3];
};

struct RawImu {
  float accel[3];
  float gyro[3];
};

struct TelemetrySummary {
  double latitudeDeg;
  double longitudeDeg;
  float altitudeM;
  float speedMps;
  float climbMps;
  float courseDeg;
  float eulerDegRpy[3];
  float batteryV;
  int linkRssiDbm;
  const char* flightState;
};

static float deviceTimeS() {
  return millis() * 0.001f;
}

static void quatToEulerDegRpy(const float qIn[4], float eulerDegRpy[3]) {
  float w = qIn[0];
  float x = qIn[1];
  float y = qIn[2];
  float z = qIn[3];
  const float norm = sqrtf(w * w + x * x + y * y + z * z);
  if (norm > 0.0f) {
    w /= norm;
    x /= norm;
    y /= norm;
    z /= norm;
  }

  const float roll = atan2f(
    2.0f * (w * x + y * z),
    1.0f - 2.0f * (x * x + y * y)
  );
  const float pitchArg = fmaxf(-1.0f, fminf(1.0f, 2.0f * (w * y - z * x)));
  const float pitch = asinf(pitchArg);
  const float yaw = atan2f(
    2.0f * (w * z + x * y),
    1.0f - 2.0f * (y * y + z * z)
  );

  eulerDegRpy[0] = roll * 57.2957795f;
  eulerDegRpy[1] = pitch * 57.2957795f;
  eulerDegRpy[2] = yaw * 57.2957795f;
}

static void sendPacket(const char* json) {
  udp.beginPacket(PC_IP, PC_UDP_PORT);
  udp.write(reinterpret_cast<const uint8_t*>(json), strlen(json));
  udp.endPacket();
}

static void writeLocalLog(const char* json) {
#if ENABLE_LOCAL_LOG
  if (!localLog) {
    return;
  }
  if (!localLog.println(json)) {
    localLogWriteErrors++;
    return;
  }
  localLogLinesSinceFlush++;
  const uint32_t nowMs = millis();
  if (nowMs - lastLocalLogFlushMs >= LOCAL_LOG_FLUSH_PERIOD_MS) {
    localLog.flush();
    localLogLinesSinceFlush = 0;
    lastLocalLogFlushMs = nowMs;
  }
#else
  (void)json;
#endif
}

static void emitPacket(const char* json) {
  sendPacket(json);
  writeLocalLog(json);
}

static void emitTelemetrySummaryPacket(const char* json) {
#if TELEMETRY_SUMMARY_TO_UDP
  sendPacket(json);
#endif
#if TELEMETRY_SUMMARY_TO_RADIO_SERIAL
  Serial2.println(json);
#endif
  writeLocalLog(json);
}

static bool beginLocalLogStorage() {
#if !ENABLE_LOCAL_LOG
  return false;
#elif USE_SD_LOG
  if (!SD.begin(SD_CS_PIN)) {
    Serial.println("Local log: SD init failed");
    return false;
  }
  localLogFs = &SD;
  return true;
#elif USE_LITTLEFS_LOG
  if (!LittleFS.begin(true)) {
    Serial.println("Local log: LittleFS init failed");
    return false;
  }
  localLogFs = &LittleFS;
  return true;
#else
  return false;
#endif
}

static bool openNextLocalLog() {
#if ENABLE_LOCAL_LOG
  if (localLog) {
    return true;
  }
  if (localLogFs == nullptr && !beginLocalLogStorage()) {
    return false;
  }
  if (!localLogFs->exists("/logs")) {
    localLogFs->mkdir("/logs");
  }
  for (uint16_t index = 0; index < 1000; index++) {
    snprintf(localLogPath, sizeof(localLogPath), "/logs/eskf_%03u.jsonl", index);
    if (!localLogFs->exists(localLogPath)) {
      localLog = localLogFs->open(localLogPath, FILE_WRITE);
      if (!localLog) {
        Serial.println("Local log: open failed");
        return false;
      }
      lastLocalLogFlushMs = millis();
      localLogLinesSinceFlush = 0;
      Serial.print("Local log: ");
      Serial.println(localLogPath);
      return true;
    }
  }
  Serial.println("Local log: no free filename");
#endif
  return false;
}

static void flushLocalLog() {
  if (localLog) {
    localLog.flush();
    localLogLinesSinceFlush = 0;
    lastLocalLogFlushMs = millis();
  }
}

static void closeLocalLog() {
  if (!localLog) {
    return;
  }
  localLog.flush();
  localLog.close();
  Serial.print("Local log closed: ");
  Serial.println(localLogPath);
}

static bool localLogActive() {
  return static_cast<bool>(localLog);
}

static void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Arduino IP: ");
  Serial.println(WiFi.localIP());
  udp.begin(LOCAL_UDP_PORT);
}

static void beginRadioSerial() {
#if TELEMETRY_SUMMARY_TO_RADIO_SERIAL
  Serial2.begin(RADIO_SERIAL_BAUD, SERIAL_8N1, RADIO_RX_PIN, RADIO_TX_PIN);
  Serial.println("Telemetry summary radio serial enabled");
#endif
}

static void ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

static void handleSerialCommand(const String& command) {
  if (command == "STOP_LOG") {
    closeLocalLog();
    return;
  }
  if (command == "START_LOG") {
    openNextLocalLog();
    return;
  }
  if (command == "FLUSH_LOG") {
    flushLocalLog();
    Serial.println("Local log flushed");
    return;
  }
  if (command == "STATUS") {
    Serial.print("WiFi: ");
    Serial.println(WiFi.status() == WL_CONNECTED ? "connected" : "disconnected");
    Serial.print("Local log active: ");
    Serial.println(localLogActive() ? "yes" : "no");
    Serial.print("Local log path: ");
    Serial.println(localLogPath[0] ? localLogPath : "-");
    Serial.print("Local log write errors: ");
    Serial.println(localLogWriteErrors);
    return;
  }
  if (command.length() > 0) {
    Serial.println("Commands: STATUS, FLUSH_LOG, STOP_LOG, START_LOG");
  }
}

static void pollSerialCommands() {
  while (Serial.available() > 0) {
    char c = static_cast<char>(Serial.read());
    if (c == '\r') {
      continue;
    }
    if (c == '\n') {
      serialCommand.trim();
      handleSerialCommand(serialCommand);
      serialCommand = "";
      continue;
    }
    if (serialCommand.length() < 48) {
      serialCommand += c;
    }
  }
}

static void readEskfState(EskfState& state) {
  // TODO: Replace with the existing Arduino ESKF state:
  // x_est = [p_est, v_est, q_est, b_a_est, b_g_est].
  const float t = deviceTimeS();
  state.p[0] = 0.5f * sinf(0.2f * t);
  state.p[1] = 0.5f * cosf(0.2f * t);
  state.p[2] = 0.0f;
  state.v[0] = 0.1f * cosf(0.2f * t);
  state.v[1] = -0.1f * sinf(0.2f * t);
  state.v[2] = 0.0f;
  const float yawRad = 0.25f * sinf(0.4f * t);
  state.q[0] = cosf(0.5f * yawRad);
  state.q[1] = 0.0f;
  state.q[2] = 0.0f;
  state.q[3] = sinf(0.5f * yawRad);
  state.ba[0] = 0.0f;
  state.ba[1] = 0.0f;
  state.ba[2] = 0.0f;
  state.bg[0] = 0.0f;
  state.bg[1] = 0.0f;
  state.bg[2] = 0.0f;
}

static void readRawImu(RawImu& imu) {
  // TODO: Replace with calibrated/raw IMU values from the flight controller.
  imu.accel[0] = 0.0f;
  imu.accel[1] = 0.0f;
  imu.accel[2] = 9.80665f;
  imu.gyro[0] = 0.0f;
  imu.gyro[1] = 0.0f;
  imu.gyro[2] = 0.0f;
}

static void readTelemetrySummary(TelemetrySummary& telemetry) {
  // TODO: Replace with GNSS, barometer, battery monitor and link-quality data.
  // Keep this packet compact; it is meant for long-range live monitoring.
  const float t = deviceTimeS();
  telemetry.latitudeDeg = 48.204680 + 0.000010 * sinf(0.05f * t);
  telemetry.longitudeDeg = 16.172000 + 0.000010 * cosf(0.05f * t);
  telemetry.altitudeM = 291.0f;
  telemetry.speedMps = 0.0f;
  telemetry.climbMps = 0.0f;
  telemetry.courseDeg = 0.0f;
  telemetry.eulerDegRpy[0] = 0.0f;
  telemetry.eulerDegRpy[1] = 0.0f;
  telemetry.eulerDegRpy[2] = 14.3f * sinf(0.4f * t);
  telemetry.batteryV = 11.7f;
  telemetry.linkRssiDbm = WiFi.status() == WL_CONNECTED ? static_cast<int>(WiFi.RSSI()) : -127;
  telemetry.flightState = "bench";
}

static void sendTelemetrySummary(const TelemetrySummary& telemetry) {
  char json[512];
  snprintf(
    json,
    sizeof(json),
    "{\"schema_version\":\"1.0\",\"message_type\":\"TELEMETRY_SUMMARY\",\"source\":\"ARDUINO\","
    "\"device_time_s\":%.6f,\"sequence\":%lu,"
    "\"payload\":{\"latitude_deg\":%.7f,\"longitude_deg\":%.7f,\"altitude_m\":%.2f,"
    "\"speed_mps\":%.2f,\"climb_mps\":%.2f,\"course_deg\":%.1f,"
    "\"euler_deg_rpy\":[%.2f,%.2f,%.2f],"
    "\"battery_v\":%.2f,\"link_rssi_dbm\":%d,\"flight_state\":\"%s\"}}",
    deviceTimeS(),
    static_cast<unsigned long>(sequenceNumber++),
    telemetry.latitudeDeg,
    telemetry.longitudeDeg,
    telemetry.altitudeM,
    telemetry.speedMps,
    telemetry.climbMps,
    telemetry.courseDeg,
    telemetry.eulerDegRpy[0],
    telemetry.eulerDegRpy[1],
    telemetry.eulerDegRpy[2],
    telemetry.batteryV,
    telemetry.linkRssiDbm,
    telemetry.flightState
  );
  emitTelemetrySummaryPacket(json);
}

static void sendEstimatorState(const EskfState& state) {
  float eulerDegRpy[3];
  quatToEulerDegRpy(state.q, eulerDegRpy);

  char json[896];
  snprintf(
    json,
    sizeof(json),
    "{\"schema_version\":\"1.0\",\"message_type\":\"ESTIMATOR_STATE\",\"source\":\"ARDUINO\","
    "\"device_time_s\":%.6f,\"sequence\":%lu,"
    "\"payload\":{\"position_m\":[%.6f,%.6f,%.6f],\"velocity_mps\":[%.6f,%.6f,%.6f],"
    "\"quaternion_wxyz\":[%.8f,%.8f,%.8f,%.8f],"
    "\"euler_deg_rpy\":[%.2f,%.2f,%.2f],"
    "\"accel_bias_mps2\":[%.6f,%.6f,%.6f],\"gyro_bias_radps\":[%.8f,%.8f,%.8f]}}",
    deviceTimeS(),
    static_cast<unsigned long>(sequenceNumber++),
    state.p[0], state.p[1], state.p[2],
    state.v[0], state.v[1], state.v[2],
    state.q[0], state.q[1], state.q[2], state.q[3],
    eulerDegRpy[0], eulerDegRpy[1], eulerDegRpy[2],
    state.ba[0], state.ba[1], state.ba[2],
    state.bg[0], state.bg[1], state.bg[2]
  );
  emitPacket(json);
}

static void sendRawImu(const RawImu& imu) {
  char json[384];
  snprintf(
    json,
    sizeof(json),
    "{\"schema_version\":\"1.0\",\"message_type\":\"RAW_SENSOR\",\"source\":\"ARDUINO\","
    "\"device_time_s\":%.6f,\"sequence\":%lu,"
    "\"payload\":{\"accel_mps2\":[%.6f,%.6f,%.6f],\"gyro_radps\":[%.8f,%.8f,%.8f]}}",
    deviceTimeS(),
    static_cast<unsigned long>(sequenceNumber++),
    imu.accel[0], imu.accel[1], imu.accel[2],
    imu.gyro[0], imu.gyro[1], imu.gyro[2]
  );
  emitPacket(json);
}

static void sendDiagnostic() {
  char json[512];
  snprintf(
    json,
    sizeof(json),
    "{\"schema_version\":\"1.0\",\"message_type\":\"FILTER_DIAGNOSTIC\",\"source\":\"ARDUINO\","
    "\"device_time_s\":%.6f,\"sequence\":%lu,"
    "\"payload\":{\"wifi_rssi_dbm\":%d,\"free_heap_bytes\":%lu,\"tracking_state\":\"running\","
    "\"local_log_active\":%s,\"local_log_path\":\"%s\",\"local_log_write_errors\":%lu}}",
    deviceTimeS(),
    static_cast<unsigned long>(sequenceNumber++),
    static_cast<int>(WiFi.RSSI()),
    static_cast<unsigned long>(ESP.getFreeHeap()),
    localLogActive() ? "true" : "false",
    localLogPath,
    static_cast<unsigned long>(localLogWriteErrors)
  );
  emitPacket(json);
}

void setup() {
  Serial.begin(115200);
  delay(200);
  beginRadioSerial();
  openNextLocalLog();
  connectWifi();
}

void loop() {
  pollSerialCommands();
  ensureWifi();
  const uint32_t nowMs = millis();

#if ENABLE_TELEMETRY_SUMMARY
  if (nowMs - lastTelemetrySummaryMs >= TELEMETRY_SUMMARY_PERIOD_MS) {
    lastTelemetrySummaryMs = nowMs;
    TelemetrySummary telemetry;
    readTelemetrySummary(telemetry);
    sendTelemetrySummary(telemetry);
  }
#endif

  if (nowMs - lastEstimatorMs >= ESTIMATOR_PERIOD_MS) {
    lastEstimatorMs = nowMs;
    EskfState state;
    readEskfState(state);
    sendEstimatorState(state);
  }

  if (nowMs - lastRawImuMs >= RAW_IMU_PERIOD_MS) {
    lastRawImuMs = nowMs;
    RawImu imu;
    readRawImu(imu);
    sendRawImu(imu);
  }

  if (nowMs - lastDiagnosticMs >= DIAGNOSTIC_PERIOD_MS) {
    lastDiagnosticMs = nowMs;
    sendDiagnostic();
  }
}
