// Minimal JSONL protocol example for the Arduino side.
// Replace the placeholder values with your existing ESKF outputs.

unsigned long sequenceNumber = 0;

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

static void printVec3(const float v[3]) {
  Serial.print("[");
  Serial.print(v[0], 6); Serial.print(",");
  Serial.print(v[1], 6); Serial.print(",");
  Serial.print(v[2], 6);
  Serial.print("]");
}

static void printQuat(const float q[4]) {
  Serial.print("[");
  Serial.print(q[0], 8); Serial.print(",");
  Serial.print(q[1], 8); Serial.print(",");
  Serial.print(q[2], 8); Serial.print(",");
  Serial.print(q[3], 8);
  Serial.print("]");
}

static void printEstimatorState(
  float t,
  const float p[3],
  const float v[3],
  const float q[4],
  const float ba[3],
  const float bg[3]
) {
  float eulerDegRpy[3];
  quatToEulerDegRpy(q, eulerDegRpy);

  Serial.print("{\"schema_version\":\"1.0\",\"message_type\":\"ESTIMATOR_STATE\",\"source\":\"ARDUINO\"");
  Serial.print(",\"device_time_s\":"); Serial.print(t, 6);
  Serial.print(",\"sequence\":"); Serial.print(sequenceNumber++);
  Serial.print(",\"payload\":{\"position_m\":"); printVec3(p);
  Serial.print(",\"velocity_mps\":"); printVec3(v);
  Serial.print(",\"quaternion_wxyz\":"); printQuat(q);
  Serial.print(",\"euler_deg_rpy\":"); printVec3(eulerDegRpy);
  Serial.print(",\"accel_bias_mps2\":"); printVec3(ba);
  Serial.print(",\"gyro_bias_radps\":"); printVec3(bg);
  Serial.println("}}");
}

static void printRawImu(float t, const float accel[3], const float gyro[3]) {
  Serial.print("{\"schema_version\":\"1.0\",\"message_type\":\"RAW_SENSOR\",\"source\":\"ARDUINO\"");
  Serial.print(",\"device_time_s\":"); Serial.print(t, 6);
  Serial.print(",\"sequence\":"); Serial.print(sequenceNumber++);
  Serial.print(",\"payload\":{\"accel_mps2\":"); printVec3(accel);
  Serial.print(",\"gyro_radps\":"); printVec3(gyro);
  Serial.println("}}");
}

void setup() {
  Serial.begin(115200);
}

void loop() {
  const float t = millis() * 0.001f;

  float p[3] = {0.0f, 0.0f, 0.0f};
  float v[3] = {0.0f, 0.0f, 0.0f};
  const float yawRad = 0.25f * sinf(0.5f * t);
  float q[4] = {cosf(0.5f * yawRad), 0.0f, 0.0f, sinf(0.5f * yawRad)};
  float ba[3] = {0.0f, 0.0f, 0.0f};
  float bg[3] = {0.0f, 0.0f, 0.0f};
  float accel[3] = {0.0f, 0.0f, 9.81f};
  float gyro[3] = {0.0f, 0.0f, 0.0f};

  printEstimatorState(t, p, v, q, ba, bg);
  printRawImu(t, accel, gyro);
  delay(20);
}
