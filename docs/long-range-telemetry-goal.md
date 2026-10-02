# Long-Range Telemetry Goal

Dieses Dokument haelt das naechste technische Ziel fest: Live-Telemetrie eines
Fluggeraets ueber groessere Distanz zum Laptop.

## Zielbild

```text
Fluggeraet -> Langstreckenfunk -> Bodenstation -> Laptop
```

Das normale WLAN zwischen Fluggeraet und Laptop reicht fuer groessere Distanzen
typischerweise nicht aus. Deshalb soll das Fluggeraet nur eine kompakte
Live-Telemetrie senden. Die vollstaendige hochfrequente Aufzeichnung bleibt
lokal auf dem Fluggeraet, z.B. auf SD-Karte.

## Rollen

### Fluggeraet

Das Fluggeraet erzeugt:

- ESKF-/Navigationszustand
- GPS-Position
- Hoehe
- Geschwindigkeit
- Batteriestatus
- Link-/Systemdiagnose

Es sendet fuer die Live-Verfolgung nur eine kompakte Zusammenfassung, z.B.
`TELEMETRY_SUMMARY`.

Parallel zeichnet es vollstaendig lokal auf:

```text
SD-Karte oder Flash/LittleFS
```

### Funkstrecke

Moegliche Funkwege:

- LoRa
- 433/868/915-MHz-Telemetrie-Funkmodule
- Mobilfunk/LTE
- Long-range WiFi mit Richtantennen

Fuer Live-Telemetrie sind geringe Datenraten akzeptabel, solange Position,
Hoehe, Geschwindigkeit und Status regelmaessig ankommen.

### Bodenstation

Die Bodenstation besitzt das passende Empfangsmodul:

```text
LoRa-/Telemetrie-Empfaenger
```

Sie leitet die empfangenen Daten laptopfreundlich weiter:

```text
USB-Serial -> Laptop
oder UDP/WLAN -> Laptop
oder Ethernet -> Laptop
```

### Laptop

Der Laptop empfaengt und speichert die Daten mit der bestehenden Python-Seite:

```powershell
python -m eskf_ref log --serial COM3 --baud 115200 --out ..\logs\flight_live.jsonl
```

oder bei UDP:

```powershell
python -m eskf_ref log --udp-host 0.0.0.0 --udp-port 5555 --out ..\logs\flight_live.jsonl
```

## Vorgeschlagener Pakettyp

Ein kompakter Pakettyp fuer grosse Distanz:

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

Dieser Pakettyp ist fuer Live-Monitoring gedacht. Er ersetzt nicht die lokale
Blackbox-Aufzeichnung.

## Typische Datenrate

Empfohlene Live-Raten:

```text
1 Hz: minimale Positionsverfolgung
5 Hz: gute Live-Anzeige fuer Position, Hoehe und Geschwindigkeit
10 Hz: fluessigere Telemetrie, falls Funkstrecke genug Reserve hat
```

Nicht ueber grosse Distanz live senden:

- hochfrequente IMU-Rohdaten
- komplette JSONL-Dateien
- volle Debug-Streams

Diese Daten gehoeren auf die lokale Blackbox.

## Offene Entscheidungen mit Kollegen

1. Welches Funkmodul soll verwendet werden?
   - LoRa
   - 433/868/915-MHz-Telemetrie
   - Mobilfunk/LTE
   - Long-range WiFi

2. Welche Frequenz ist rechtlich und praktisch passend?

3. Welche Reichweite wird benoetigt?

4. Welche Update-Rate wird benoetigt?
   - 1 Hz
   - 5 Hz
   - 10 Hz

5. Soll die Bodenstation per USB-Serial oder UDP/WLAN an den Laptop gehen?

6. Welche Werte sind fuer die Live-Anzeige zwingend?
   - Position
   - Hoehe
   - Geschwindigkeit
   - Steig-/Sinkrate
   - Batterie
   - Flugzustand
   - Linkqualitaet

7. Wie wird die lokale Blackbox nach dem Flug ausgelesen?
   - SD-Karte
   - USB
   - HTTP/WLAN
   - anderer Transferweg

## Aktueller Projektstand

Bereits vorhanden:

- Android Live-UDP zum Laptop
- Android lokale `.jsonl.gz` Blackbox
- Android kompletter Datei-Upload nach `Stop`
- ESP32/Arduino UDP-Telemetrie-Beispiel
- ESP32/Arduino lokale SD-/LittleFS-Blackbox vorbereitet
- `TELEMETRY_SUMMARY` als Protokolltyp vorbereitet
- ESP32-Erzeugung von `TELEMETRY_SUMMARY` vorbereitet
- einfache ESP32-Bodenstations-Bridge Serial2 -> USB/UDP vorbereitet
- Python-Logger fuer UDP und Serial

Noch zu implementieren:

- Live-Ansicht/Kartenansicht auf Laptop
- Auswahl und Test eines realen Langstrecken-Funkmoduls
- echte GPS-/Batterie-/Linkdaten in `readTelemetrySummary(...)` einsetzen
- Bodenstations-Bridge mit realem Funkmodul testen
