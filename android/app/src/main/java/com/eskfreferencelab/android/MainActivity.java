package com.eskfreferencelab.android;

import android.Manifest;
import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.ArrayAdapter;
import android.widget.Spinner;
import android.widget.TextView;

public class MainActivity extends Activity {
    private static final int REQUEST_RUNTIME_PERMISSIONS = 42;

    private EditText hostInput;
    private EditText portInput;
    private EditText uploadPortInput;
    private CheckBox udpToggle;
    private CheckBox uploadToggle;
    private Spinner profileInput;
    private TextView statusText;
    private TextView sequenceText;
    private TextView locationText;
    private TextView positionText;
    private TextView altitudeText;
    private TextView speedText;
    private TextView accelerationText;
    private TextView logFileText;
    private Button startButton;
    private Button stopButton;
    private boolean running = false;

    private final BroadcastReceiver statusReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            running = intent.getBooleanExtra(RecordingService.EXTRA_RUNNING, running);
            setControls(running);
            updateStatus(intent.getStringExtra(RecordingService.EXTRA_STATUS));
            sequenceText.setText("Sequence: " + intent.getLongExtra(RecordingService.EXTRA_SEQUENCE, 0));
            String location = intent.getStringExtra(RecordingService.EXTRA_LOCATION);
            if (location != null) {
                locationText.setText("Location summary: " + location);
            }
            String position = intent.getStringExtra(RecordingService.EXTRA_POSITION_DETAILS);
            if (position != null) {
                positionText.setText(position);
            }
            String altitude = intent.getStringExtra(RecordingService.EXTRA_ALTITUDE_DETAILS);
            if (altitude != null) {
                altitudeText.setText(altitude);
            }
            String speed = intent.getStringExtra(RecordingService.EXTRA_SPEED_DETAILS);
            if (speed != null) {
                speedText.setText(speed);
            }
            String acceleration = intent.getStringExtra(RecordingService.EXTRA_ACCEL_DETAILS);
            if (acceleration != null) {
                accelerationText.setText(acceleration);
            }
            String logPath = intent.getStringExtra(RecordingService.EXTRA_LOG_PATH);
            if (logPath != null) {
                logFileText.setText("Log file: " + logPath);
            }
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(buildUi());
        updateStatus("stopped");
    }

    @Override
    protected void onResume() {
        super.onResume();
        IntentFilter filter = new IntentFilter(RecordingService.ACTION_STATUS);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(statusReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(statusReceiver, filter);
        }
        sendBroadcast(new Intent(RecordingService.ACTION_REQUEST_STATUS).setPackage(getPackageName()));
    }

    @Override
    protected void onPause() {
        unregisterReceiver(statusReceiver);
        super.onPause();
    }

    private ScrollView buildUi() {
        ScrollView scrollView = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(36, 44, 36, 36);
        scrollView.addView(root);

        TextView title = new TextView(this);
        title.setText("ESKF Reference");
        title.setTextSize(26);
        title.setTextColor(Color.rgb(28, 34, 44));
        title.setGravity(Gravity.START);
        root.addView(title, matchWrap());

        TextView subtitle = new TextView(this);
        subtitle.setText("Foreground recording service for Android sensors and location");
        subtitle.setTextSize(14);
        subtitle.setTextColor(Color.rgb(86, 94, 108));
        subtitle.setPadding(0, 6, 0, 24);
        root.addView(subtitle, matchWrap());

        hostInput = labeledInput(root, "PC IP address", "192.168.1.100", InputType.TYPE_CLASS_TEXT);
        portInput = labeledInput(root, "UDP port", "5555", InputType.TYPE_CLASS_NUMBER);
        uploadPortInput = labeledInput(root, "Upload port", "8766", InputType.TYPE_CLASS_NUMBER);

        udpToggle = new CheckBox(this);
        udpToggle.setText("UDP zum PC senden");
        udpToggle.setChecked(false);
        udpToggle.setPadding(0, 12, 0, 4);
        root.addView(udpToggle, matchWrap());

        uploadToggle = new CheckBox(this);
        uploadToggle.setText("Nach Stop komplette Logdatei senden");
        uploadToggle.setChecked(false);
        uploadToggle.setPadding(0, 4, 0, 4);
        root.addView(uploadToggle, matchWrap());

        TextView profileLabel = new TextView(this);
        profileLabel.setText("Log profile");
        profileLabel.setTextSize(13);
        profileLabel.setTextColor(Color.rgb(74, 83, 98));
        profileLabel.setPadding(0, 14, 0, 4);
        root.addView(profileLabel, matchWrap());

        profileInput = new Spinner(this);
        ArrayAdapter<String> profileAdapter = new ArrayAdapter<>(
                this,
                android.R.layout.simple_spinner_dropdown_item,
                new String[] {
                        "Balanced",
                        "State + Location",
                        "Full Debug"
                }
        );
        profileInput.setAdapter(profileAdapter);
        profileInput.setSelection(0);
        root.addView(profileInput, matchWrap());

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setPadding(0, 16, 0, 16);
        root.addView(row, matchWrap());

        startButton = new Button(this);
        startButton.setText("Start");
        startButton.setOnClickListener(v -> startRecording());
        row.addView(startButton, weightedButton());

        stopButton = new Button(this);
        stopButton.setText("Stop");
        stopButton.setEnabled(false);
        stopButton.setOnClickListener(v -> stopRecording());
        row.addView(stopButton, weightedButton());

        statusText = valueText(root, "Status");
        sequenceText = valueText(root, "Sequence");
        locationText = valueText(root, "Location summary");
        locationText.setText("Location summary: no fix");
        positionText = valueText(root, "Position");
        positionText.setText("Breitengrad: -\nLaengengrad: -");
        altitudeText = valueText(root, "Hoehe");
        altitudeText.setText("Hoehe: -");
        speedText = valueText(root, "Geschwindigkeit");
        speedText.setText("Geschwindigkeit: -");
        accelerationText = valueText(root, "Beschleunigung");
        accelerationText.setText("Beschleunigung: -");
        logFileText = valueText(root, "Log file");
        logFileText.setText("Log file: -");

        TextView note = new TextView(this);
        note.setText("Die Aufnahme laeuft als Foreground Service weiter, auch wenn das Display ausgeht. Fuer lange Tests Akkuoptimierung fuer diese App deaktivieren.");
        note.setTextSize(13);
        note.setTextColor(Color.rgb(100, 91, 64));
        note.setPadding(0, 24, 0, 0);
        root.addView(note, matchWrap());

        return scrollView;
    }

    private EditText labeledInput(LinearLayout root, String label, String value, int inputType) {
        TextView labelView = new TextView(this);
        labelView.setText(label);
        labelView.setTextSize(13);
        labelView.setTextColor(Color.rgb(74, 83, 98));
        labelView.setPadding(0, 14, 0, 4);
        root.addView(labelView, matchWrap());

        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setText(value);
        input.setInputType(inputType);
        root.addView(input, matchWrap());
        return input;
    }

    private TextView valueText(LinearLayout root, String label) {
        TextView value = new TextView(this);
        value.setText(label + ": -");
        value.setTextSize(15);
        value.setTextColor(Color.rgb(28, 34, 44));
        value.setPadding(0, 10, 0, 0);
        root.addView(value, matchWrap());
        return value;
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        );
    }

    private LinearLayout.LayoutParams weightedButton() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1);
        params.setMargins(0, 0, 12, 0);
        return params;
    }

    private void startRecording() {
        if (!hasRequiredPermissions()) {
            requestRuntimePermissions();
            return;
        }

        Intent intent = new Intent(this, RecordingService.class);
        intent.setAction(RecordingService.ACTION_START);
        intent.putExtra(RecordingService.EXTRA_UDP_ENABLED, udpToggle.isChecked());
        intent.putExtra(RecordingService.EXTRA_UDP_HOST, hostInput.getText().toString().trim());
        intent.putExtra(RecordingService.EXTRA_UDP_PORT, Integer.parseInt(portInput.getText().toString().trim()));
        intent.putExtra(RecordingService.EXTRA_UPLOAD_ON_STOP, uploadToggle.isChecked());
        intent.putExtra(RecordingService.EXTRA_UPLOAD_PORT, Integer.parseInt(uploadPortInput.getText().toString().trim()));
        intent.putExtra(RecordingService.EXTRA_LOG_PROFILE, selectedProfile());
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent);
        } else {
            startService(intent);
        }
    }

    private void stopRecording() {
        Intent intent = new Intent(this, RecordingService.class);
        intent.setAction(RecordingService.ACTION_STOP);
        startService(intent);
    }

    private void setControls(boolean isRunning) {
        startButton.setEnabled(!isRunning);
        stopButton.setEnabled(isRunning);
        hostInput.setEnabled(!isRunning);
        portInput.setEnabled(!isRunning);
        uploadPortInput.setEnabled(!isRunning);
        udpToggle.setEnabled(!isRunning);
        uploadToggle.setEnabled(!isRunning);
        profileInput.setEnabled(!isRunning);
    }

    private void updateStatus(String status) {
        if (status != null && statusText != null) {
            statusText.setText("Status: " + status);
        }
    }

    private String selectedProfile() {
        int position = profileInput.getSelectedItemPosition();
        if (position == 1) {
            return RecordingService.LOG_PROFILE_STATE_LOCATION;
        }
        if (position == 2) {
            return RecordingService.LOG_PROFILE_FULL;
        }
        return RecordingService.LOG_PROFILE_BALANCED;
    }

    private boolean hasRequiredPermissions() {
        boolean location = checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
                || checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
        boolean notifications = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU
                || checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED;
        return location && notifications;
    }

    private void requestRuntimePermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            requestPermissions(
                    new String[] {
                            Manifest.permission.ACCESS_FINE_LOCATION,
                            Manifest.permission.ACCESS_COARSE_LOCATION,
                            Manifest.permission.POST_NOTIFICATIONS
                    },
                    REQUEST_RUNTIME_PERMISSIONS
            );
        } else {
            requestPermissions(
                    new String[] {
                            Manifest.permission.ACCESS_FINE_LOCATION,
                            Manifest.permission.ACCESS_COARSE_LOCATION
                    },
                    REQUEST_RUNTIME_PERMISSIONS
            );
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_RUNTIME_PERMISSIONS && hasRequiredPermissions()) {
            startRecording();
        }
    }
}
