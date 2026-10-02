# Coordinate Frames

State-Vergleiche sind erst gueltig, nachdem Zeitbasis und Frames ausgerichtet
wurden.

## Festzulegen

- Arduino Body Frame: Achsenrichtung am MPU6050.
- iPhone Device Frame: Achsenrichtung des befestigten iPhones.
- ARKit World Frame: lokaler Start-Frame der ARSession.
- Navigationsframe: ENU oder NED.
- Quaternion-Reihenfolge: dieses Projekt nutzt `[w, x, y, z]`.
- Quaternion-Richtung: explizit dokumentieren, ob Body-to-World oder
  World-to-Body.

## Kalibrierparameter

```text
T_phone_arduino = { R_phone_arduino, t_phone_arduino }
```

Dabei beschreibt `R_phone_arduino` die feste Rotation zwischen den
Sensor-Frames und `t_phone_arduino` den Lever Arm.

## MVP-Regel

Fuer die erste Auswertung reicht eine statische Rotationskalibrierung plus
ein gemeinsamer lokaler Ursprung. Bei schnellen Rotationen muss der Lever Arm
beruecksichtigt werden, da sonst Positions- und Geschwindigkeitsfehler durch
die Montagegeometrie entstehen.
