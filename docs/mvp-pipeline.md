# MVP Pipeline

## Aufnahme

1. iPhone und Arduino starr verbinden.
2. PC-Logger starten.
3. iOS-App mit PC-IP und UDP-Port starten.
4. Arduino per USB verbinden und JSONL-State-Ausgabe aktivieren.
5. Einige Sekunden ruhen lassen, dann definierte Rotationen und Translationen
   ausfuehren.

## Offline-Verarbeitung

1. `RAW_SENSOR` Gyro-Normen von iPhone und Arduino extrahieren.
2. Zeitoffset per Kreuzkorrelation schaetzen.
3. Arduino-Zeit in iPhone-Referenzzeit transformieren.
4. Frames kalibrieren und State-Groessen transformieren.
5. `ESTIMATOR_STATE` und `REFERENCE_STATE` zeitlich paaren.
6. RMSE, Maximalfehler, Drift und Orientierungsfehler berechnen.
7. Tracking-Status und Filterdiagnostik als Qualitaetsfilter nutzen.

## Aktuelle Auswertebefehle

Speicherbedarf und Nachrichtenraten schaetzen:

```powershell
python -m eskf_ref stats --input ..\logs\android_balanced_123.jsonl.gz
```

State-vs-State-Auswertung mit optionaler Gyro-Zeitsynchronisation:

```powershell
python -m eskf_ref evaluate `
  --input ..\logs\run.jsonl.gz `
  --reference-source ANDROID `
  --estimator-source ARDUINO `
  --sync-from-gyro `
  --csv-out ..\logs\errors.csv `
  --plots-dir ..\logs\plots
```

Wenn noch kein Arduino-`ESTIMATOR_STATE` im Log vorhanden ist, gibt der Befehl
eine klare Notiz aus und berechnet noch keine State-Fehler.

## Nicht-Ziele im MVP

- Kein neuer ESKF.
- Keine perfekte Ground Truth.
- Keine Roh-IMU-Integration als iPhone-Referenz.
- Kein App-Store-Release.
