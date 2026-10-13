# Android Test App

Diese App streamt Android-Sensorfusion und Roh-IMU per UDP an den Python-PC-Logger.
Sie kann zusaetzlich ohne WLAN lokal auf dem Android-Geraet als JSONL aufzeichnen.
Die Aufzeichnung laeuft als Android Foreground Service mit sichtbarer
Notification und WakeLock, damit sie auch bei ausgeschaltetem Display weiterlaeuft.
Lokale Dateien werden als komprimierte `.jsonl.gz` geschrieben.

## Was Android im MVP liefert

- `REFERENCE_STATE` mit Orientierung aus `TYPE_ROTATION_VECTOR`
- Fallback auf `TYPE_GAME_ROTATION_VECTOR`
- Live-Anzeige von Quaternion und Roll/Pitch/Yaw-Winkeln
- GNSS/Network-Location mit `speed_mps`
- `velocity_mps` aus Android-Speed und Bearing, falls verfuegbar
- `RAW_SENSOR` mit Accelerometer und Gyroscope
- `position_available=false`
- `velocity_available=true`, sobald Android Location-Speed liefert
- lokale JSONL-Aufzeichnung unter dem app-eigenen Dateipfad

Android liefert ohne ARCore/visuelle Odometrie keine lokale 3D-Position wie ARKit.
Fuer den ersten Geraetetest ist diese App deshalb fuer Orientierung, GNSS-Speed,
UDP, Zeitstempel, Roh-IMU und Logger-Integration gedacht.

## Log-Profile

Die Log-Profile bestimmen, wie dicht die App lokal speichert und live per UDP
sendet:

- `Balanced`: Standardprofil fuer normale Feldtests. Es schreibt
  `REFERENCE_STATE` mit ca. 10 Hz, `RAW_SENSOR`/IMU mit ca. 25 Hz und Location
  mit ca. 1 Hz. Das ist der beste Kompromiss aus Dateigroesse und Analysewert.
- `State + Location`: kleineres Profil fuer lange Wege oder reine
  GPS-/Geschwindigkeitspruefung. Es schreibt `REFERENCE_STATE` mit ca. 5 Hz und
  Location mit ca. 1 Hz, aber keine Raw-IMU. Dadurch fehlen Gyro-/Accel-Details
  fuer Synchronisation und Debugging.
- `Full Debug`: Detailprofil fuer kurze Tests. Es schreibt `REFERENCE_STATE`
  mit ca. 20 Hz, `RAW_SENSOR`/IMU mit ca. 50 Hz und Location mit ca. 2 Hz. Dieses
  Profil erzeugt die groessten Dateien.

## Start

1. App auf dem Android-Geraet starten.
2. `UDP zum PC senden` ausgeschaltet lassen.
3. `Start` druecken und Location-Berechtigung erlauben.
4. Die Benachrichtigung `ESKF Reference recording` sichtbar lassen.
5. Aufzeichnung stoppen.
6. Die App zeigt den lokalen Log-Dateipfad an.

Fuer lange Tests: In Androids Akku-Einstellungen die Batterieoptimierung fuer
`ESKF Reference` deaktivieren bzw. `Uneingeschraenkt` erlauben. Einige Hersteller
beenden selbst Foreground Services aggressiv, wenn Akku-Sparen aktiv ist.

Typischer Pfad auf dem Geraet:

```text
Android/data/com.eskfreferencelab.android/files/logs/android_<timestamp>.jsonl
```

Neue Dateien heissen inzwischen:

```text
Android/data/com.eskfreferencelab.android/files/logs/android_<profile>_<timestamp>.jsonl.gz
```

## Start mit PC-Logger per WLAN

1. PC und Android-Geraet ins gleiche WLAN bringen.
2. Python-Logger fuer Live-UDP starten:

   ```powershell
   cd C:\Users\ceyhu\AndroidStudioProjects\EskfReferenceLab\python
   $env:PYTHONPATH='src'
   python -m eskf_ref log --udp-host 0.0.0.0 --udp-port 5555 --out ..\logs\android_test.jsonl
   ```

3. Optional den HTTP-Empfaenger fuer die komplette Logdatei nach `Stop` starten:

   ```powershell
   python -m eskf_ref receive-file --host 0.0.0.0 --port 8766 --out-dir ..\logs\uploads
   ```

4. In Android Studio den Ordner `C:\Users\ceyhu\AndroidStudioProjects\EskfReferenceLab\android` oeffnen.
5. App auf dem Android-Geraet starten.
6. In der App `UDP zum PC senden` aktivieren.
7. In der App die PC-IP und UDP-Port `5555` eintragen.
8. Optional `Nach Stop komplette Logdatei senden` aktivieren und Upload-Port `8766` eintragen.
9. `Start` druecken und Location-Berechtigung erlauben.

UDP ist fuer Live-Monitoring gedacht und darf bei WLAN-Verlust Pakete verlieren.
Der optionale Upload nach `Stop` sendet dagegen die lokal gespeicherte `.jsonl.gz`
als komplette Datei an den PC.

## Build per Kommandozeile

```powershell
cd C:\Users\ceyhu\AndroidStudioProjects\EskfReferenceLab\android
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
$env:PATH="$env:JAVA_HOME\bin;$env:PATH"
.\gradlew.bat assembleDebug
```

Debug-APK:

```text
android\app\build\outputs\apk\debug\app-debug.apk
```

Komprimierte Logs koennen direkt mit der Python-Auswertung gelesen werden:

```powershell
python -m eskf_ref analyze --input ..\logs\android_balanced_1234567890.jsonl.gz
```

## Einschraenkung

Zeitsync gegen Arduino-Rohgyro:

```powershell
python -m eskf_ref sync --input ..\logs\android_test.jsonl --reference-source ANDROID --moving-source ARDUINO
```

Der State-Vergleich `p_est/v_est/q_est` gegen `p_ref/v_ref/q_ref` ist mit dieser
Android-MVP-App fuer `q_ref` und grobe horizontale GNSS-Velocity sinnvoll.
Fuer echte lokale Position und visuell-inertiale 3D-Geschwindigkeit waere als
naechster Schritt eine ARCore-basierte Android-App noetig.
