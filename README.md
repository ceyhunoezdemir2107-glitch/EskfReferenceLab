# ESKF Reference Lab

MVP-Projekt fuer eine reproduzierbare Mess-, Logging- und Auswerteumgebung
zum Tuning eines bestehenden Arduino-ESKF.

Die zentrale Leitlinie ist:

```text
Arduino ESKF State <-> iPhone Reference State
Rohsensoren werden nur ergaenzend fuer Synchronisation, Diagnose und Debugging genutzt.
```

## Ziel

Das System vergleicht den bereits auf dem Arduino geschaetzten Zustand

```text
x_est = [p_est, v_est, q_est, b_a_est, b_g_est]
```

mit einem vom iPhone bereits fusionierten Referenzzustand

```text
x_ref = [p_ref, v_ref, q_ref]
```

Die iPhone-Referenz stammt primaer aus ARKit Visual-Inertial Tracking und
Core Motion. Sie ist ein Reference State, keine perfekte Ground Truth.

## Komponenten

- `ios/ReferenceStateStreamer`: Swift-Startpunkt fuer eine lokale iOS-App,
  die ARKit/CoreMotion-States und optionale Rohsensoren per UDP sendet.
- `android`: Native Android-Test-App, die Android-Sensorfusion
  (`TYPE_ROTATION_VECTOR`), Quaternion, Roll/Pitch/Yaw-Winkel und Roh-IMU per
  UDP sendet.
- `flutter/reference_state_client`: Flutter-Quellvorlage fuer eine spaetere
  iOS/Web-App mit Quaternion- und Roll/Pitch/Yaw-Ausgabe.
- `web`: Browser-Testoberflaeche fuer Reference-State/Raw-Sensor-Simulation.
- `python`: PC-Logger und Offline-Auswertung fuer UDP + Serial.
- `arduino`: Beispiele fuer Arduino/ESP32 JSON-Telemetrie ueber Serial,
  WLAN/UDP und eine einfache Bodenstations-Bridge.
- `schemas`: maschinenlesbares JSON-Schema fuer Log- und Netzwerkpakete.
- `docs`: technische Spezifikationen fuer Datenformat, Frames und MVP.

Die praktische Schritt-fuer-Schritt-Anleitung fuer Feldtests steht in
`FIELD_TEST_README.md`.

Das Zielbild fuer groessere Flugdistanz mit Langstreckenfunk und Bodenstation
steht in `docs/long-range-telemetry-goal.md`.

## Orientierung und Winkel

Die Orientierung wird im gesamten Projekt primaer als Quaternion gespeichert:

```json
"quaternion_wxyz": [w, x, y, z]
```

Fuer Live-Anzeige und schnelle Plausibilitaetspruefung wird zusaetzlich ein
Hilfsfeld mit Roll, Pitch und Yaw in Grad verwendet:

```json
"euler_deg_rpy": [roll_deg, pitch_deg, yaw_deg]
```

Aktueller Stand:

- Android zeigt Quaternion und Roll/Pitch/Yaw live in der App und speichert beide
  Felder im `REFERENCE_STATE`.
- Arduino/ESP32 sendet `quaternion_wxyz` und `euler_deg_rpy` im
  `ESTIMATOR_STATE`; `TELEMETRY_SUMMARY` enthaelt die kompakten Winkel fuer
  Live-Monitoring ueber Funk/Bodenstation.
- iOS Swift/ARKit berechnet die Winkel aus der ARKit-Quaternion, zeigt sie an
  und sendet sie im `REFERENCE_STATE`.
- Web-Testoberflaeche zeigt Quaternion und Winkel an und sendet beide Felder.
- Flutter ist als Quellvorlage fuer iOS/Web vorbereitet und erzeugt dasselbe
  Payload-Format.

Wichtig: Fuer den eigentlichen State-vs-State-Vergleich bleibt
`quaternion_wxyz` massgeblich. `euler_deg_rpy` ist ein abgeleitetes Komfortfeld.

## Android Log-Profile

Die Android-App bietet drei Profile fuer Aufzeichnung und Live-UDP:

- `Balanced`: Standardprofil fuer normale Feldtests. Es schreibt
  `REFERENCE_STATE` mit ca. 10 Hz, `RAW_SENSOR`/IMU mit ca. 25 Hz und Location
  mit ca. 1 Hz. Das ist der beste Kompromiss aus Dateigroesse und spaeterer
  Analyse.
- `State + Location`: kleineres Profil fuer lange Wege oder reine
  GPS-/Geschwindigkeitspruefung. Es schreibt `REFERENCE_STATE` mit ca. 5 Hz und
  Location mit ca. 1 Hz, aber keine Raw-IMU. Dadurch fehlen Gyro-/Accel-Details
  fuer Synchronisation und Debugging.
- `Full Debug`: Detailprofil fuer kurze Tests. Es schreibt `REFERENCE_STATE`
  mit ca. 20 Hz, `RAW_SENSOR`/IMU mit ca. 50 Hz und Location mit ca. 2 Hz. Dieses
  Profil erzeugt die groessten Dateien.

Fuer normale Android-Tests zuerst `Balanced` verwenden. Fuer lange
GPS-/Geschwindigkeitsaufzeichnungen ist `State + Location` sparsamer.

## MVP-Datenfluss

```text
iPhone ARKit/CoreMotion -> REFERENCE_STATE -> UDP -> Python JSONL log
Android RotationVector  -> REFERENCE_STATE -> UDP -> Python JSONL log
Web Browser/Simulator   -> REFERENCE_STATE -> HTTP -> Python JSONL log
Arduino ESKF            -> ESTIMATOR_STATE -> USB/UDP -> Python JSONL log
Arduino/iPhone IMU      -> RAW_SENSOR      -> JSONL log, Offline-Sync
Flutter iOS/Web Client  -> REFERENCE_STATE -> vorbereitetes Payload-Format
```

Hinweis: Die Android-MVP-App liefert ohne ARCore nur Orientierung als
Reference-State. Die Orientierung wird als `quaternion_wxyz` gespeichert und
in der App zusaetzlich als Roll/Pitch/Yaw-Winkel angezeigt. Fuer vollstaendige
Android-VIO waere der naechste Schritt ARCore.

## Web-Test starten

```powershell
cd C:\Users\ceyhu\AndroidStudioProjects\EskfReferenceLab\python
$env:PYTHONPATH='src'
python -m eskf_ref web --host 127.0.0.1 --port 8765 --out ..\logs\web_test.jsonl
```

Dann im Browser oeffnen:

```text
http://127.0.0.1:8765
```

Der Web-Test nutzt HTTP statt UDP, weil Browser kein UDP senden duerfen.

Jede empfangene Nachricht wird vom PC um einen monotonen Empfangszeitstempel
`pc_recv_time_s` erweitert und als JSON Lines geschrieben.

## Python quick start

```powershell
cd EskfReferenceLab\python
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
python -m eskf_ref log --udp-host 0.0.0.0 --udp-port 5555 --serial COM3 --baud 115200 --out ..\logs\run.jsonl
```

Ohne Arduino kann der Logger auch nur UDP empfangen:

```powershell
python -m eskf_ref log --udp-port 5555 --out ..\logs\iphone_only.jsonl
```

Arduino/ESP32 per WLAN kann denselben UDP-Port nutzen:

```powershell
python -m eskf_ref log --udp-host 0.0.0.0 --udp-port 5555 --out ..\logs\arduino_live.jsonl
```

Der ESP32-Beispielsketch kann parallel lokal auf SD-Karte oder LittleFS schreiben.
Damit entspricht er dem Android-Prinzip: UDP fuer Live-Monitoring, lokale JSONL-
Datei als Blackbox fuer die vollstaendige Nachanalyse.

Analyse:

```powershell
python -m eskf_ref analyze --input ..\logs\run.jsonl
python -m eskf_ref sync --input ..\logs\run.jsonl --max-lag-s 2.0
python -m eskf_ref stats --input ..\logs\android_balanced_123.jsonl.gz
python -m eskf_ref evaluate --input ..\logs\run.jsonl.gz --reference-source ANDROID --estimator-source ARDUINO --sync-from-gyro --csv-out ..\logs\errors.csv --plots-dir ..\logs\plots
```

`stats` ist fuer schnelle Feldtests gedacht: Es zeigt Dateigroesse,
Nachrichtenraten und geschaetzte MB pro Stunde. `evaluate` fuehrt den
eigentlichen State-vs-State-Vergleich aus, sobald im Log sowohl
`REFERENCE_STATE` als auch Arduino-`ESTIMATOR_STATE` enthalten sind.

## Pakettypen

- `REFERENCE_STATE`: iPhone fusionierter State, bevorzugt ARKit/CoreMotion.
- `ESTIMATOR_STATE`: Arduino-ESKF-State.
- `RAW_SENSOR`: Gyro/Accelerometer/Baro/GNSS-Roh- oder Naeherungsdaten.
- `FILTER_DIAGNOSTIC`: Innovationen, NIS, Kovarianzen, Gating.
- `CLOCK_SYNC`: optionale Zeit- oder Sequenz-Marker.

Diese Trennung ist absichtlich streng, damit Rohdaten spaeter nicht
versehentlich als Referenz-State ausgewertet werden.

## Naechste praktische Schritte

1. Python-Logger lokal starten.
2. iOS Swift-Dateien in ein Xcode-iOS-App-Projekt einfuegen und UDP-Ziel
   auf die PC-IP setzen.
3. Arduino-Ausgabe auf das JSONL-Protokoll anpassen oder
   `arduino/esp32_udp_telemetry_example.ino` als WLAN-UDP-Startpunkt nutzen.
4. Einen kurzen starren Bewegungsversuch aufnehmen.
5. Gyro-Kreuzkorrelation zur Zeitsynchronisation ausfuehren.
6. Frames kalibrieren und erst danach State-vs-State-Metriken bewerten.
