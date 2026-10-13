# Flutter Reference State Client

Vorbereiteter Flutter-Startpunkt fuer iOS und Web.

Dieser Ordner enthaelt bewusst nur die Flutter-Quellen und kein generiertes
Platform-Scaffold. Sobald Flutter installiert ist:

```powershell
cd C:\Users\ceyhu\AndroidStudioProjects\EskfReferenceLab\flutter\reference_state_client
flutter create .
flutter run -d chrome
```

Auf macOS kann derselbe Ordner fuer iOS verwendet werden:

```bash
flutter create .
flutter run -d ios
```

Die App zeigt Roll, Pitch, Yaw, berechnet daraus `quaternion_wxyz` und erzeugt
einen `REFERENCE_STATE`-Payload mit `euler_deg_rpy`. Spaeter koennen hier
Sensor-Plugins und UDP/HTTP-Transport ergaenzt werden.
