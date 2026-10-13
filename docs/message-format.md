# Message Format

Alle Netzwerk-, Serial- und Logdaten verwenden eine JSON-Nachricht pro Zeile
oder UDP-Paket. Der PC schreibt JSON Lines.

## Envelope

```json
{
  "schema_version": "1.0",
  "message_type": "REFERENCE_STATE",
  "source": "IPHONE",
  "device_time_s": 123.456,
  "sequence": 42,
  "payload": {}
}
```

Der Logger ergaenzt:

```json
{
  "pc_recv_time_s": 9876.543,
  "transport": "udp"
}
```

## REFERENCE_STATE

Vom iPhone bereits geschaetzter/fusionierter Referenzzustand.

```json
{
  "schema_version": "1.0",
  "message_type": "REFERENCE_STATE",
  "source": "IPHONE",
  "device_time_s": 10.02,
  "sequence": 121,
  "payload": {
    "state_source": "ARKit",
    "position_m": [0.12, -0.03, 1.44],
    "velocity_mps": [0.41, 0.00, -0.02],
    "quaternion_wxyz": [0.99, 0.01, 0.03, 0.02],
    "euler_deg_rpy": [1.2, 3.4, 2.1],
    "tracking_state": "normal"
  }
}
```

`quaternion_wxyz` ist das primaere Orientierungsformat. `euler_deg_rpy` ist ein
zusaetzliches Hilfsfeld fuer Anzeige und schnelle Plausibilitaetspruefung:
Roll, Pitch, Yaw in Grad, aus dem Quaternion abgeleitet.

## ESTIMATOR_STATE

Arduino-State aus dem bestehenden ESKF.

```json
{
  "schema_version": "1.0",
  "message_type": "ESTIMATOR_STATE",
  "source": "ARDUINO",
  "device_time_s": 10.01,
  "sequence": 981,
  "payload": {
    "position_m": [0.11, -0.02, 1.43],
    "velocity_mps": [0.39, 0.01, -0.03],
    "quaternion_wxyz": [0.99, 0.01, 0.03, 0.02],
    "euler_deg_rpy": [1.1, 3.2, 2.0],
    "accel_bias_mps2": [0.01, -0.02, 0.05],
    "gyro_bias_radps": [0.001, 0.0, -0.002]
  }
}
```

## RAW_SENSOR

Rohdaten duerfen fuer Synchronisation und Diagnose genutzt werden, aber nicht
als State-Referenz.

```json
{
  "schema_version": "1.0",
  "message_type": "RAW_SENSOR",
  "source": "ARDUINO",
  "device_time_s": 10.01,
  "sequence": 982,
  "payload": {
    "gyro_radps": [0.1, -0.2, 0.0],
    "accel_mps2": [0.0, 0.1, 9.81]
  }
}
```

## TELEMETRY_SUMMARY

Kompakte Live-Telemetrie fuer groessere Distanzen. Dieses Paket ist fuer
Monitoring, Wiederfinden und Bodenstationsanzeige gedacht. Hochfrequente Rohdaten
bleiben in der lokalen Blackbox.

```json
{
  "schema_version": "1.0",
  "message_type": "TELEMETRY_SUMMARY",
  "source": "ARDUINO",
  "device_time_s": 123.45,
  "sequence": 812,
  "payload": {
    "latitude_deg": 48.20468,
    "longitude_deg": 16.17200,
    "altitude_m": 291.4,
    "speed_mps": 12.8,
    "climb_mps": 1.2,
    "course_deg": 84.0,
    "battery_v": 11.7,
    "link_rssi_dbm": -82,
    "flight_state": "flying"
  }
}
```

## FILTER_DIAGNOSTIC

```json
{
  "schema_version": "1.0",
  "message_type": "FILTER_DIAGNOSTIC",
  "source": "ARDUINO",
  "device_time_s": 10.01,
  "payload": {
    "sensor": "gnss",
    "innovation": [0.4, -0.1, 0.2],
    "nis": 2.1,
    "gated": false
  }
}
```
