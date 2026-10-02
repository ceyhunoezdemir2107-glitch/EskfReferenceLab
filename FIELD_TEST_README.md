# Field Test Workflow

Diese Anleitung beschreibt den aktuellen getesteten Ablauf fuer Android-Handy,
Laptop und spaeter ESP32/Arduino-Fluggeraet.

## Grundprinzip

Das System nutzt zwei Datenwege:

```text
Live-UDP:
  schnelle Telemetrie zum Laptop, Paketverlust ist erlaubt

Lokale Blackbox:
  vollstaendige Aufzeichnung auf dem Geraet fuer die spaetere Analyse
```

Beim Android-Handy wird die lokale Blackbox als `.jsonl.gz` geschrieben. Nach
`Stop` kann diese Datei optional per HTTP zum Laptop hochgeladen werden.

Beim ESP32/Arduino ist das gleiche Prinzip vorbereitet: Live-UDP zum Laptop und
lokale JSONL-Datei auf SD-Karte oder LittleFS.

## Laptop vorbereiten

1. Laptop-IP im WLAN pruefen:

   ```powershell
   ipconfig
   ```

   Die getestete WLAN-IP war:

   ```text
   192.168.0.112
   ```

2. Live-UDP-Empfaenger starten:

   ```powershell
   cd C:\Users\ceyhu\AndroidStudioProjects\EskfReferenceLab\python
   $env:PYTHONPATH='src'
   python -m eskf_ref log --udp-host 0.0.0.0 --udp-port 5555 --udp-recv-buffer-mb 8 --status-interval-s 2 --out ..\logs\live_test.jsonl
   ```

3. Datei-Upload-Empfaenger starten:

   ```powershell
   cd C:\Users\ceyhu\AndroidStudioProjects\EskfReferenceLab\python
   $env:PYTHONPATH='src'
   python -m eskf_ref receive-file --host 0.0.0.0 --port 8766 --out-dir ..\logs\uploads
   ```

4. Falls Windows Firewall fragt: Python fuer private Netzwerke erlauben.

## Android-App einstellen

Auf dem Handy:

```text
PC IP address: 192.168.0.112
UDP port: 5555
Upload port: 8766
UDP zum PC senden: an
Nach Stop komplette Logdatei senden: an
```

Dann:

```text
Start -> aufnehmen -> Stop
```

Die App zeigt auf dem Hauptbildschirm unter anderem:

```text
Breitengrad
Laengengrad
Hoehe in m
Geschwindigkeit in m/s und km/h
Beschleunigung x/y/z und Betrag
lokaler Log-Dateipfad
```

Hinweis: Die Android-Beschleunigung enthaelt aktuell auch Gravitation. Im
Stillstand ist der Betrag deshalb typischerweise nahe `9.81 m/s2`.

## Android Log-Profile

Die App bietet mehrere Log-Profile. Sie bestimmen, wie viele Nachrichten lokal
gespeichert und live per UDP gesendet werden.

```text
Balanced
  Standardprofil fuer normale Feldtests.
  Schreibt REFERENCE_STATE mit ca. 10 Hz und RAW_SENSOR/IMU mit ca. 25 Hz.
  Location/GPS wird mit ca. 1 Hz aktualisiert, sobald Android neue Werte liefert.
  Dieses Profil ist der beste Kompromiss aus Dateigroesse und spaeterer Analyse.

State + Location
  Kleineres Log fuer lange Wege oder reine GPS-/Geschwindigkeitspruefung.
  Schreibt REFERENCE_STATE mit ca. 5 Hz und Location/GPS mit ca. 1 Hz.
  RAW_SENSOR/IMU wird nicht gespeichert.
  Dadurch sind die Dateien deutlich kleiner, aber Gyro-/Accel-Details fuer
  Synchronisation und Debugging fehlen.

Full Debug
  Detailprofil fuer kurze Tests.
  Schreibt REFERENCE_STATE mit ca. 20 Hz, RAW_SENSOR/IMU mit ca. 50 Hz und
  Location/GPS mit ca. 2 Hz.
  Dieses Profil erzeugt die groessten Dateien und ist vor allem zum Debuggen
  von Sensorverhalten, Paketfluss und Zeitstempeln gedacht.
```

Fuer normale Tests zuerst `Balanced` verwenden. `State + Location` ist sinnvoll,
wenn die Aufzeichnung lange laufen soll und primaer Ort, Hoehe und Geschwindigkeit
interessieren. `Full Debug` nur verwenden, wenn wirklich mehr Sensordetails
gebraucht werden.

## Wo die Dateien liegen

Live-UDP auf dem Laptop:

```text
C:\Users\ceyhu\AndroidStudioProjects\EskfReferenceLab\logs\live_test.jsonl
```

Kompletter Upload nach `Stop` auf dem Laptop:

```text
C:\Users\ceyhu\AndroidStudioProjects\EskfReferenceLab\logs\uploads\
```

Lokale Android-Blackbox auf dem Handy:

```text
/sdcard/Android/data/com.eskfreferencelab.android/files/logs/
```

Beispiel:

```text
android_balanced_1790957917667.jsonl.gz
```

## Erfolg pruefen

Live-Datei pruefen:

```powershell
python -m eskf_ref stats --input ..\logs\live_test.jsonl
```

Upload-Datei pruefen:

```powershell
python -m eskf_ref stats --input ..\logs\uploads\android_balanced_123.jsonl.gz
```

Bei einem erfolgreichen Test sieht man:

```text
source: ANDROID
REFERENCE_STATE und RAW_SENSOR
message_count > 0
bad_lines = 0
```

Im Live-Empfaenger sind besonders wichtig:

```text
msg/s      aktuelle Empfangsrate
gaps       Sequenzluecken im UDP-Stream
errors     unlesbare Pakete
```

`gaps=0` bedeutet, dass der Live-Stream in diesem Abschnitt keine erkannten
Sequenzluecken hatte. Bei Funk- oder WLAN-Abbruch sind `gaps > 0` normal.

## Verhalten bei Verbindungsabbruch

Wenn WLAN oder Funk weg ist:

```text
Live-UDP zum Laptop kann ausfallen oder Luecken haben.
Die lokale Blackbox auf dem Geraet laeuft weiter, solange Geraet und App laufen.
```

Wenn das Geraet spaeter wiedergefunden wird, kann die lokale Datei vom Geraet
geholt und ausgewertet werden. Das ist der entscheidende Sicherheitsgewinn.

## Android-Logs per USB holen

Wenn das Handy per USB verbunden ist:

```powershell
C:\Users\ceyhu\AppData\Local\Android\Sdk\platform-tools\adb.exe shell ls -lh /sdcard/Android/data/com.eskfreferencelab.android/files/logs
```

Datei ziehen:

```powershell
C:\Users\ceyhu\AppData\Local\Android\Sdk\platform-tools\adb.exe pull /sdcard/Android/data/com.eskfreferencelab.android/files/logs/android_balanced_123.jsonl.gz C:\Users\ceyhu\AndroidStudioProjects\EskfReferenceLab\logs\pulled\
```

## ESP32 / Arduino

Der vorbereitete Sketch liegt hier:

```text
C:\Users\ceyhu\AndroidStudioProjects\EskfReferenceLab\arduino\esp32_udp_telemetry_example.ino
```

Er sendet live:

```text
ESTIMATOR_STATE
RAW_SENSOR
FILTER_DIAGNOSTIC
```

und kann lokal schreiben:

```text
SD-Karte: bevorzugt fuer Flugtests
LittleFS: kurze Bench-Tests ohne SD-Karte
```

Die zu ersetzenden Stellen im Sketch sind:

```cpp
readEskfState(...)
readRawImu(...)
```

Dort werden spaeter die echten ESKF- und IMU-Werte des Fluggeraets eingesetzt.

## Spaetere Auswertung

Sobald ein gemeinsames Log Android/iOS-Referenz und Arduino-ESKF enthaelt:

```powershell
python -m eskf_ref evaluate --input ..\logs\run.jsonl --reference-source ANDROID --estimator-source ARDUINO --sync-from-gyro --csv-out ..\logs\errors.csv --plots-dir ..\logs\plots
```

Der Vergleich ist ein State-vs-State-Vergleich:

```text
REFERENCE_STATE gegen ESTIMATOR_STATE
```

Rohsensoren werden nur fuer Synchronisation und Diagnose genutzt.
