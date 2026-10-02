package com.eskfreferencelab.android;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.io.OutputStreamWriter;
import java.io.FileOutputStream;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.HttpURLConnection;
import java.net.InetAddress;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicLong;
import java.util.zip.GZIPOutputStream;

public class RecordingService extends Service implements SensorEventListener, LocationListener {
    public static final String ACTION_START = "com.eskfreferencelab.android.START";
    public static final String ACTION_STOP = "com.eskfreferencelab.android.STOP";
    public static final String ACTION_STATUS = "com.eskfreferencelab.android.STATUS";
    public static final String ACTION_REQUEST_STATUS = "com.eskfreferencelab.android.REQUEST_STATUS";
    public static final String EXTRA_UDP_ENABLED = "udp_enabled";
    public static final String EXTRA_UDP_HOST = "udp_host";
    public static final String EXTRA_UDP_PORT = "udp_port";
    public static final String EXTRA_UPLOAD_ON_STOP = "upload_on_stop";
    public static final String EXTRA_UPLOAD_PORT = "upload_port";
    public static final String EXTRA_LOG_PROFILE = "log_profile";
    public static final String EXTRA_RUNNING = "running";
    public static final String EXTRA_STATUS = "status";
    public static final String EXTRA_SEQUENCE = "sequence";
    public static final String EXTRA_LOCATION = "location";
    public static final String EXTRA_POSITION_DETAILS = "position_details";
    public static final String EXTRA_ALTITUDE_DETAILS = "altitude_details";
    public static final String EXTRA_SPEED_DETAILS = "speed_details";
    public static final String EXTRA_ACCEL_DETAILS = "accel_details";
    public static final String EXTRA_LOG_PATH = "log_path";
    public static final String LOG_PROFILE_BALANCED = "balanced";
    public static final String LOG_PROFILE_STATE_LOCATION = "state_location";
    public static final String LOG_PROFILE_FULL = "full";

    private static final String CHANNEL_ID = "recording";
    private static final int NOTIFICATION_ID = 10;

    private final AtomicLong sequence = new AtomicLong(0);
    private final ExecutorService udpExecutor = Executors.newSingleThreadExecutor();
    private final ExecutorService uploadExecutor = Executors.newSingleThreadExecutor();

    private SensorManager sensorManager;
    private LocationManager locationManager;
    private Sensor rotationSensor;
    private Sensor gameRotationSensor;
    private Sensor accelerometer;
    private Sensor gyroscope;
    private PowerManager.WakeLock wakeLock;

    private volatile boolean recording = false;
    private volatile Location latestLocation;
    private volatile String status = "stopped";
    private volatile String locationSummary = "no fix";
    private volatile String positionDetails = "Breitengrad/Laengengrad: -";
    private volatile String altitudeDetails = "Hoehe: -";
    private volatile String speedDetails = "Geschwindigkeit: -";
    private volatile String accelDetails = "Beschleunigung: -";
    private volatile String logPath;
    private volatile InetAddress targetAddress;
    private volatile int targetPort = 5555;
    private volatile boolean uploadOnStop = false;
    private volatile String uploadHost;
    private volatile int uploadPort = 8766;
    private volatile boolean stopping = false;
    private DatagramSocket socket;
    private BufferedWriter localLogWriter;
    private String logProfile = LOG_PROFILE_BALANCED;
    private double minReferenceDtS = 0.10;
    private double minRawImuDtS = 0.04;
    private double minLocationDtS = 1.00;
    private boolean logRawImu = true;
    private double lastReferenceLogS = -1.0;
    private double lastGyroLogS = -1.0;
    private double lastAccelLogS = -1.0;
    private double lastLocationLogS = -1.0;
    private double lastUiBroadcastS = -1.0;

    @Override
    public void onCreate() {
        super.onCreate();
        sensorManager = (SensorManager) getSystemService(SENSOR_SERVICE);
        locationManager = (LocationManager) getSystemService(LOCATION_SERVICE);
        rotationSensor = sensorManager.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR);
        gameRotationSensor = sensorManager.getDefaultSensor(Sensor.TYPE_GAME_ROTATION_VECTOR);
        accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER);
        gyroscope = sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE);
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent != null ? intent.getAction() : null;
        if (ACTION_STOP.equals(action)) {
            boolean waitingForUpload = stopRecording(true);
            if (!waitingForUpload) {
                stopSelf();
            }
            return START_NOT_STICKY;
        }
        if (ACTION_REQUEST_STATUS.equals(action)) {
            broadcastStatus();
            return recording ? START_STICKY : START_NOT_STICKY;
        }
        if (ACTION_START.equals(action) && !recording) {
            boolean udpEnabled = intent.getBooleanExtra(EXTRA_UDP_ENABLED, false);
            String host = intent.getStringExtra(EXTRA_UDP_HOST);
            int port = intent.getIntExtra(EXTRA_UDP_PORT, 5555);
            boolean uploadEnabled = intent.getBooleanExtra(EXTRA_UPLOAD_ON_STOP, false);
            int selectedUploadPort = intent.getIntExtra(EXTRA_UPLOAD_PORT, 8766);
            String profile = intent.getStringExtra(EXTRA_LOG_PROFILE);
            configureLogProfile(profile);
            startRecording(udpEnabled, host, port, uploadEnabled, selectedUploadPort);
        }
        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        stopRecording(false);
        udpExecutor.shutdownNow();
        uploadExecutor.shutdownNow();
        super.onDestroy();
    }

    private void startRecording(boolean udpEnabled, String host, int port, boolean uploadEnabled, int selectedUploadPort) {
        status = "starting";
        startForeground(NOTIFICATION_ID, buildNotification("starting"));
        stopping = false;
        uploadOnStop = uploadEnabled;
        uploadHost = host;
        uploadPort = selectedUploadPort;

        if (!openLocalLog()) {
            status = "log file error";
            broadcastStatus();
            stopSelf();
            return;
        }

        if (udpEnabled) {
            try {
                targetAddress = InetAddress.getByName(host);
                targetPort = port;
                socket = new DatagramSocket();
            } catch (Exception ex) {
                status = "udp target error: " + ex.getMessage();
                closeLocalLog();
                broadcastStatus();
                stopSelf();
                return;
            }
        } else {
            targetAddress = null;
            socket = null;
        }

        acquireWakeLock();
        sequence.set(0);
        resetRateLimitState();
        recording = true;
        registerSensors();
        startLocationUpdates();
        status = "recording";
        updateNotification();
        broadcastStatus();
    }

    private boolean stopRecording(boolean allowUpload) {
        if (!recording && localLogWriter == null && socket == null) {
            return false;
        }
        if (stopping) {
            return false;
        }
        stopping = true;
        String completedLogPath = logPath;
        recording = false;
        if (sensorManager != null) {
            sensorManager.unregisterListener(this);
        }
        if (locationManager != null) {
            try {
                locationManager.removeUpdates(this);
            } catch (SecurityException ignored) {
            }
        }
        if (socket != null) {
            socket.close();
            socket = null;
        }
        releaseWakeLock();
        closeLocalLog();
        if (allowUpload && uploadOnStop && completedLogPath != null) {
            File file = new File(completedLogPath);
            if (file.isFile()) {
                status = "uploading log";
                updateNotification();
                broadcastStatus();
                uploadExecutor.execute(() -> uploadClosedLogAndStop(file));
                return true;
            }
        }
        finishStopped("stopped");
        return false;
    }

    private void uploadClosedLogAndStop(File file) {
        boolean ok = uploadClosedLog(file);
        finishStopped(ok ? "upload complete" : status);
        stopSelf();
    }

    private void finishStopped(String finalStatus) {
        status = finalStatus;
        updateNotification();
        broadcastStatus();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            stopForeground(STOP_FOREGROUND_REMOVE);
        } else {
            stopForeground(true);
        }
        stopping = false;
    }

    private void registerSensors() {
        Sensor referenceSensor = rotationSensor != null ? rotationSensor : gameRotationSensor;
        if (referenceSensor != null) {
            sensorManager.registerListener(this, referenceSensor, SensorManager.SENSOR_DELAY_GAME);
        }
        if (accelerometer != null) {
            sensorManager.registerListener(this, accelerometer, SensorManager.SENSOR_DELAY_GAME);
        }
        if (gyroscope != null) {
            sensorManager.registerListener(this, gyroscope, SensorManager.SENSOR_DELAY_GAME);
        }
    }

    private void startLocationUpdates() {
        if (locationManager == null || !hasLocationPermission()) {
            locationSummary = "no permission";
            return;
        }
        try {
            if (locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                locationManager.requestLocationUpdates(LocationManager.GPS_PROVIDER, 500, 0, this);
                latestLocation = locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER);
            }
            if (locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                locationManager.requestLocationUpdates(LocationManager.NETWORK_PROVIDER, 500, 0, this);
                Location networkLocation = locationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER);
                if (latestLocation == null || (networkLocation != null && networkLocation.getTime() > latestLocation.getTime())) {
                    latestLocation = networkLocation;
                }
            }
            updateLocationSummary(latestLocation);
        } catch (SecurityException ex) {
            locationSummary = "permission error";
        }
    }

    @Override
    public void onSensorChanged(SensorEvent event) {
        if (!recording) {
            return;
        }
        double t = event.timestamp * 1e-9;
        try {
            if (event.sensor.getType() == Sensor.TYPE_ROTATION_VECTOR
                    || event.sensor.getType() == Sensor.TYPE_GAME_ROTATION_VECTOR) {
                if (!shouldLogReference(t)) {
                    return;
                }
                sendReferenceState(event, t);
            } else if (event.sensor.getType() == Sensor.TYPE_ACCELEROMETER) {
                updateAccelerationSummary(event.values);
                broadcastStatusIfDue(t);
                if (!shouldLogRawImu(t, false)) {
                    return;
                }
                sendRawSensor(t, "accel_mps2", event.values);
            } else if (event.sensor.getType() == Sensor.TYPE_GYROSCOPE) {
                if (!shouldLogRawImu(t, true)) {
                    return;
                }
                sendRawSensor(t, "gyro_radps", event.values);
            }
        } catch (JSONException ex) {
            status = "json error: " + ex.getMessage();
            broadcastStatus();
        }
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {
    }

    @Override
    public void onLocationChanged(Location location) {
        latestLocation = location;
        updateLocationSummary(location);
        if (!recording) {
            return;
        }
        double locationTimeS = location.getElapsedRealtimeNanos() * 1e-9;
        if (!shouldLogLocation(locationTimeS)) {
            return;
        }
        try {
            sendRawLocation(location);
        } catch (JSONException ex) {
            status = "location json error: " + ex.getMessage();
        }
        broadcastStatus();
    }

    private void sendReferenceState(SensorEvent event, double deviceTimeS) throws JSONException {
        float[] q = new float[4];
        SensorManager.getQuaternionFromVector(q, event.values);
        Location location = latestLocation;
        boolean hasSpeed = location != null && location.hasSpeed();

        JSONObject payload = new JSONObject();
        payload.put("state_source", event.sensor.getType() == Sensor.TYPE_ROTATION_VECTOR
                ? "AndroidRotationVector"
                : "AndroidGameRotationVector");
        payload.put("position_available", false);
        payload.put("velocity_available", hasSpeed);
        payload.put("position_m", vector(0.0, 0.0, 0.0));
        payload.put("velocity_mps", velocityFromLocation(location));
        payload.put("quaternion_wxyz", vector(q[0], q[1], q[2], q[3]));
        payload.put("tracking_state", accuracyText(event.accuracy));
        putLocationFields(payload, location);
        sendMessage("REFERENCE_STATE", deviceTimeS, payload);
    }

    private void sendRawSensor(double deviceTimeS, String field, float[] values) throws JSONException {
        JSONObject payload = new JSONObject();
        payload.put(field, vector(values[0], values[1], values[2]));
        sendMessage("RAW_SENSOR", deviceTimeS, payload);
    }

    private void sendRawLocation(Location location) throws JSONException {
        JSONObject payload = new JSONObject();
        putLocationFields(payload, location);
        if (location.hasSpeed()) {
            payload.put("speed_mps", location.getSpeed());
        }
        if (location.hasBearing()) {
            payload.put("course_deg", location.getBearing());
        }
        sendMessage("RAW_SENSOR", location.getElapsedRealtimeNanos() * 1e-9, payload);
    }

    private void sendMessage(String type, double deviceTimeS, JSONObject payload) throws JSONException {
        JSONObject message = new JSONObject();
        message.put("schema_version", "1.0");
        message.put("message_type", type);
        message.put("source", "ANDROID");
        message.put("device_time_s", deviceTimeS);
        message.put("sequence", sequence.getAndIncrement());
        message.put("payload", payload);
        String json = message.toString();
        writeLocalLog(json);
        sendUdp(json);
        if (sequence.get() % 100 == 0) {
            flushLocalLog();
            updateNotification();
            broadcastStatus();
        }
    }

    private JSONArray vector(double a, double b, double c) throws JSONException {
        return new JSONArray().put(a).put(b).put(c);
    }

    private JSONArray vector(double a, double b, double c, double d) throws JSONException {
        return new JSONArray().put(a).put(b).put(c).put(d);
    }

    private JSONArray velocityFromLocation(Location location) throws JSONException {
        if (location == null || !location.hasSpeed()) {
            return vector(0.0, 0.0, 0.0);
        }
        double speed = location.getSpeed();
        if (!location.hasBearing()) {
            return vector(speed, 0.0, 0.0);
        }
        double bearingRad = Math.toRadians(location.getBearing());
        double east = speed * Math.sin(bearingRad);
        double north = speed * Math.cos(bearingRad);
        return vector(east, north, 0.0);
    }

    private void putLocationFields(JSONObject payload, Location location) throws JSONException {
        payload.put("location_available", location != null);
        payload.put("velocity_frame", location != null && location.hasBearing() ? "ENU_APPROX" : "SPEED_ONLY");
        if (location == null) {
            return;
        }
        payload.put("location_provider", location.getProvider());
        payload.put("latitude_deg", location.getLatitude());
        payload.put("longitude_deg", location.getLongitude());
        payload.put("location_time_ms", location.getTime());
        if (location.hasAltitude()) {
            payload.put("altitude_m", location.getAltitude());
        }
        if (location.hasAccuracy()) {
            payload.put("horizontal_accuracy_m", location.getAccuracy());
        }
        if (location.hasSpeed()) {
            payload.put("speed_mps", location.getSpeed());
            if (location.hasSpeedAccuracy()) {
                payload.put("speed_accuracy_mps", location.getSpeedAccuracyMetersPerSecond());
            }
        }
        if (location.hasBearing()) {
            payload.put("course_deg", location.getBearing());
        }
    }

    private void sendUdp(String json) {
        byte[] data = json.getBytes(StandardCharsets.UTF_8);
        InetAddress address = targetAddress;
        DatagramSocket activeSocket = socket;
        int port = targetPort;
        if (address == null || activeSocket == null || activeSocket.isClosed()) {
            return;
        }
        udpExecutor.execute(() -> {
            try {
                DatagramPacket packet = new DatagramPacket(data, data.length, address, port);
                activeSocket.send(packet);
            } catch (IOException ex) {
                status = "udp error: " + ex.getMessage();
                broadcastStatus();
            }
        });
    }

    private boolean uploadClosedLog(File file) {
        HttpURLConnection connection = null;
        try {
            if (uploadHost == null || uploadHost.trim().isEmpty()) {
                status = "upload error: missing host";
                broadcastStatus();
                return false;
            }
            String encodedName = URLEncoder.encode(file.getName(), "UTF-8");
            URL url = new URL("http://" + uploadHost + ":" + uploadPort + "/upload?filename=" + encodedName);
            connection = (HttpURLConnection) url.openConnection();
            connection.setRequestMethod("POST");
            connection.setConnectTimeout(15000);
            connection.setReadTimeout(120000);
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/gzip");
            connection.setRequestProperty("X-Log-Filename", file.getName());
            connection.setFixedLengthStreamingMode(file.length());

            byte[] buffer = new byte[64 * 1024];
            try (FileInputStream input = new FileInputStream(file);
                 OutputStream output = connection.getOutputStream()) {
                int read;
                while ((read = input.read(buffer)) != -1) {
                    output.write(buffer, 0, read);
                }
            }

            int responseCode = connection.getResponseCode();
            if (responseCode >= 200 && responseCode < 300) {
                status = "upload complete";
                broadcastStatus();
                return true;
            }
            status = "upload error: HTTP " + responseCode;
            broadcastStatus();
            return false;
        } catch (Exception ex) {
            status = "upload error: " + ex.getMessage();
            broadcastStatus();
            return false;
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    private boolean openLocalLog() {
        try {
            File dir = new File(getExternalFilesDir(null), "logs");
            if (!dir.exists() && !dir.mkdirs()) {
                return false;
            }
            File file = new File(dir, String.format(Locale.US, "android_%s_%d.jsonl.gz", logProfile, System.currentTimeMillis()));
            logPath = file.getAbsolutePath();
            GZIPOutputStream gzipOutputStream = new GZIPOutputStream(new FileOutputStream(file));
            localLogWriter = new BufferedWriter(new OutputStreamWriter(gzipOutputStream, StandardCharsets.UTF_8));
            return true;
        } catch (IOException ex) {
            status = "log file error: " + ex.getMessage();
            return false;
        }
    }

    private synchronized void writeLocalLog(String json) {
        if (localLogWriter == null) {
            return;
        }
        try {
            localLogWriter.write(json);
            localLogWriter.newLine();
        } catch (IOException ex) {
            status = "log write error: " + ex.getMessage();
            broadcastStatus();
        }
    }

    private synchronized void closeLocalLog() {
        if (localLogWriter == null) {
            return;
        }
        try {
            localLogWriter.flush();
            localLogWriter.close();
        } catch (IOException ignored) {
        } finally {
            localLogWriter = null;
        }
    }

    private synchronized void flushLocalLog() {
        if (localLogWriter == null) {
            return;
        }
        try {
            localLogWriter.flush();
        } catch (IOException ex) {
            status = "log flush error: " + ex.getMessage();
            broadcastStatus();
        }
    }

    private void acquireWakeLock() {
        PowerManager powerManager = (PowerManager) getSystemService(POWER_SERVICE);
        wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "EskfReferenceLab:Recording");
        wakeLock.setReferenceCounted(false);
        wakeLock.acquire();
    }

    private void releaseWakeLock() {
        if (wakeLock != null && wakeLock.isHeld()) {
            wakeLock.release();
        }
        wakeLock = null;
    }

    private boolean hasLocationPermission() {
        return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
                || checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    private String accuracyText(int accuracy) {
        switch (accuracy) {
            case SensorManager.SENSOR_STATUS_ACCURACY_HIGH:
                return "high";
            case SensorManager.SENSOR_STATUS_ACCURACY_MEDIUM:
                return "medium";
            case SensorManager.SENSOR_STATUS_ACCURACY_LOW:
                return "low";
            case SensorManager.SENSOR_STATUS_UNRELIABLE:
                return "unreliable";
            default:
                return "unknown";
        }
    }

    private void updateLocationSummary(Location location) {
        if (location == null) {
            locationSummary = "no fix";
            positionDetails = "Breitengrad/Laengengrad: -";
            altitudeDetails = "Hoehe: -";
            speedDetails = "Geschwindigkeit: -";
            return;
        }
        String speed = location.hasSpeed()
                ? String.format(Locale.US, "%.2f m/s", location.getSpeed())
                : "no speed";
        String accuracy = location.hasAccuracy()
                ? String.format(Locale.US, ", acc %.1f m", location.getAccuracy())
                : "";
        locationSummary = speed + accuracy + ", " + location.getProvider();
        String horizontalAccuracy = location.hasAccuracy()
                ? String.format(Locale.US, ", Genauigkeit %.1f m", location.getAccuracy())
                : "";
        positionDetails = String.format(
                Locale.US,
                "Breitengrad: %.8f\nLaengengrad: %.8f\nProvider: %s%s",
                location.getLatitude(),
                location.getLongitude(),
                location.getProvider(),
                horizontalAccuracy
        );
        altitudeDetails = location.hasAltitude()
                ? String.format(Locale.US, "Hoehe: %.1f m", location.getAltitude())
                : "Hoehe: -";
        String course = location.hasBearing()
                ? String.format(Locale.US, ", Kurs %.1f deg", location.getBearing())
                : "";
        speedDetails = location.hasSpeed()
                ? String.format(Locale.US, "Geschwindigkeit: %.2f m/s (%.1f km/h)%s", location.getSpeed(), location.getSpeed() * 3.6, course)
                : "Geschwindigkeit: -";
    }

    private void updateAccelerationSummary(float[] values) {
        double magnitude = Math.sqrt(
                values[0] * values[0]
                        + values[1] * values[1]
                        + values[2] * values[2]
        );
        accelDetails = String.format(
                Locale.US,
                "Beschleunigung: x %.2f, y %.2f, z %.2f m/s2\nBetrag: %.2f m/s2",
                values[0],
                values[1],
                values[2],
                magnitude
        );
    }

    private void broadcastStatusIfDue(double deviceTimeS) {
        if (lastUiBroadcastS >= 0.0 && deviceTimeS - lastUiBroadcastS < 0.50) {
            return;
        }
        lastUiBroadcastS = deviceTimeS;
        broadcastStatus();
    }

    private void broadcastStatus() {
        Intent intent = new Intent(ACTION_STATUS).setPackage(getPackageName());
        intent.putExtra(EXTRA_RUNNING, recording);
        intent.putExtra(EXTRA_STATUS, status);
        intent.putExtra(EXTRA_SEQUENCE, sequence.get());
        intent.putExtra(EXTRA_LOCATION, locationSummary);
        intent.putExtra(EXTRA_POSITION_DETAILS, positionDetails);
        intent.putExtra(EXTRA_ALTITUDE_DETAILS, altitudeDetails);
        intent.putExtra(EXTRA_SPEED_DETAILS, speedDetails);
        intent.putExtra(EXTRA_ACCEL_DETAILS, accelDetails);
        intent.putExtra(EXTRA_LOG_PATH, logPath);
        sendBroadcast(intent);
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return;
        }
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "ESKF Recording",
                NotificationManager.IMPORTANCE_LOW
        );
        channel.setDescription("Keeps ESKF sensor recording active.");
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(channel);
    }

    private Notification buildNotification(String text) {
        Intent openIntent = new Intent(this, MainActivity.class);
        PendingIntent openPendingIntent = PendingIntent.getActivity(
                this,
                1,
                openIntent,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT
        );
        Intent stopIntent = new Intent(this, RecordingService.class);
        stopIntent.setAction(ACTION_STOP);
        PendingIntent stopPendingIntent = PendingIntent.getService(
                this,
                2,
                stopIntent,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT
        );

        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        return builder
                .setContentTitle("ESKF Reference recording")
                .setContentText(text + " | seq " + sequence.get())
                .setSmallIcon(android.R.drawable.ic_menu_compass)
                .setContentIntent(openPendingIntent)
                .setOngoing(true)
                .addAction(android.R.drawable.ic_media_pause, "Stop", stopPendingIntent)
                .build();
    }

    private void updateNotification() {
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        manager.notify(NOTIFICATION_ID, buildNotification(status));
    }

    private void configureLogProfile(String profile) {
        logProfile = profile != null ? profile : LOG_PROFILE_BALANCED;
        if (LOG_PROFILE_FULL.equals(logProfile)) {
            minReferenceDtS = 0.05;
            minRawImuDtS = 0.02;
            minLocationDtS = 0.50;
            logRawImu = true;
            return;
        }
        if (LOG_PROFILE_STATE_LOCATION.equals(logProfile)) {
            minReferenceDtS = 0.20;
            minRawImuDtS = 999999.0;
            minLocationDtS = 1.00;
            logRawImu = false;
            return;
        }
        logProfile = LOG_PROFILE_BALANCED;
        minReferenceDtS = 0.10;
        minRawImuDtS = 0.04;
        minLocationDtS = 1.00;
        logRawImu = true;
    }

    private void resetRateLimitState() {
        lastReferenceLogS = -1.0;
        lastGyroLogS = -1.0;
        lastAccelLogS = -1.0;
        lastLocationLogS = -1.0;
        lastUiBroadcastS = -1.0;
    }

    private boolean shouldLogReference(double t) {
        if (lastReferenceLogS >= 0.0 && t - lastReferenceLogS < minReferenceDtS) {
            return false;
        }
        lastReferenceLogS = t;
        return true;
    }

    private boolean shouldLogRawImu(double t, boolean gyro) {
        if (!logRawImu) {
            return false;
        }
        if (gyro) {
            if (lastGyroLogS >= 0.0 && t - lastGyroLogS < minRawImuDtS) {
                return false;
            }
            lastGyroLogS = t;
            return true;
        }
        if (lastAccelLogS >= 0.0 && t - lastAccelLogS < minRawImuDtS) {
            return false;
        }
        lastAccelLogS = t;
        return true;
    }

    private boolean shouldLogLocation(double t) {
        if (lastLocationLogS >= 0.0 && t - lastLocationLogS < minLocationDtS) {
            return false;
        }
        lastLocationLogS = t;
        return true;
    }
}
