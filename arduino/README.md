# Arduino / ESP32 Telemetry

Dieser Ordner enthaelt zwei Einstiege:

- `serial_protocol_example.ino`: JSONL-Ausgabe ueber USB/Serial.
- `esp32_udp_telemetry_example.ino`: Live-Telemetrie per WLAN/UDP zum Laptop.
- `esp32_groundstation_serial_to_udp.ino`: Bodenstations-Bridge von serieller
  Funkstrecke zu USB-Serial und/oder UDP.

## ESP32 per WLAN/UDP und lokaler Blackbox

1. Im Sketch WLAN und Laptop-IP setzen:

   ```cpp
   const char* WIFI_SSID = "YOUR_WIFI_SSID";
   const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
   IPAddress PC_IP(192, 168, 0, 112);
   const uint16_t PC_UDP_PORT = 5555;
   ```

2. Lokales Logging waehlen. Fuer Flugtests ist SD-Karte der Standard:

   ```cpp
   #define ENABLE_LOCAL_LOG 1
   #define USE_SD_LOG 1
   #define USE_LITTLEFS_LOG 0
   const int SD_CS_PIN = 5;
   ```

   Fuer kurze Bench-Tests ohne SD-Karte kann LittleFS/Flash verwendet werden:

   ```cpp
   #define ENABLE_LOCAL_LOG 1
   #define USE_SD_LOG 0
   #define USE_LITTLEFS_LOG 1
   ```

3. Kompakte Langstrecken-Telemetrie ist vorbereitet:

   ```cpp
   #define ENABLE_TELEMETRY_SUMMARY 1
   #define TELEMETRY_SUMMARY_TO_UDP 1
   #define TELEMETRY_SUMMARY_TO_RADIO_SERIAL 0
   ```

   Fuer ein transparentes serielles Funkmodul kann spaeter `Serial2` aktiviert
   werden:

   ```cpp
   #define TELEMETRY_SUMMARY_TO_RADIO_SERIAL 1
   ```

4. Auf dem Laptop den Logger starten:

   ```powershell
   cd C:\Users\ceyhu\AndroidStudioProjects\EskfReferenceLab\python
   $env:PYTHONPATH='src'
   python -m eskf_ref log --udp-host 0.0.0.0 --udp-port 5555 --out ..\logs\arduino_live.jsonl
   ```

5. Sketch auf den ESP32 flashen.

Der Logger sollte dann `source=ARDUINO` mit `transport=udp` empfangen. In der
Live-Ausgabe sind `msg/s`, `gaps` und `errors` sichtbar.

Parallel schreibt der ESP32 lokal eine JSONL-Datei:

```text
/logs/eskf_000.jsonl
/logs/eskf_001.jsonl
...
```

Die Datei ist absichtlich unkomprimiert, damit der Mikrocontroller wenig Arbeit
hat. Nach dem Kopieren auf den Laptop kann sie dort bei Bedarf komprimiert oder
direkt ausgewertet werden.

## Serial-Kommandos

Im Serial Monitor koennen folgende Kommandos gesendet werden:

```text
STATUS
FLUSH_LOG
STOP_LOG
START_LOG
```

Vor dem Entfernen der SD-Karte nach einem Test sollte `STOP_LOG` gesendet oder
der ESP32 sauber ausgeschaltet werden. `STOP_LOG` schliesst die lokale JSONL-
Datei. Ein spaeterer Datei-Transfer per HTTP, TCP, SD-Kartenleser oder USB-Mass-
Storage kann auf dieser Datei aufsetzen.

## Was ersetzt werden muss

Im UDP-Sketch sind nur diese beiden Funktionen projektspezifisch:

```cpp
static void readEskfState(EskfState& state)
static void readRawImu(RawImu& imu)
```

Dort werden die bestehenden Flugcontroller-/ESKF-Werte eingesetzt:

```text
p_est, v_est, q_est, b_a_est, b_g_est
accel_mps2, gyro_radps
```

Fuer Langstrecken-Telemetrie zusaetzlich:

```cpp
static void readTelemetrySummary(TelemetrySummary& telemetry)
```

Dort werden GPS, Hoehe, Geschwindigkeit, Batterie, Linkqualitaet und Flugzustand
eingesetzt.

## Bodenstation

Wenn das Fluggeraet `TELEMETRY_SUMMARY` ueber ein transparentes serielles
Funkmodul sendet, kann `esp32_groundstation_serial_to_udp.ino` als einfache
Bodenstation dienen:

```text
Funkmodul -> ESP32 Serial2 -> USB-Serial und/oder UDP -> Laptop
```

Laptop per USB-Serial:

```powershell
python -m eskf_ref log --serial COM3 --baud 115200 --out ..\logs\flight_live.jsonl
```

Laptop per UDP:

```powershell
python -m eskf_ref log --udp-host 0.0.0.0 --udp-port 5555 --out ..\logs\flight_live.jsonl
```

## Gemeinsames Log mit Android/iOS-Referenz

Wenn Android oder iOS parallel an denselben Python-Logger sendet, landen die
Pakete in derselben JSONL-Datei:

```text
ANDROID REFERENCE_STATE
ARDUINO ESTIMATOR_STATE
ARDUINO RAW_SENSOR
```

Danach kann der State-Vergleich laufen:

```powershell
python -m eskf_ref evaluate --input ..\logs\arduino_live.jsonl --reference-source ANDROID --estimator-source ARDUINO --sync-from-gyro --csv-out ..\logs\errors.csv --plots-dir ..\logs\plots
```

UDP ist fuer Live-Monitoring gedacht. Paketverlust bei Funk- oder WLAN-Problemen
ist normal und wird ueber `sequence`-Luecken sichtbar.
