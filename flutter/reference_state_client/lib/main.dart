import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';

void main() {
  runApp(const ReferenceStateClientApp());
}

class ReferenceStateClientApp extends StatelessWidget {
  const ReferenceStateClientApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'ESKF Reference',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff246b5a)),
        useMaterial3: true,
      ),
      home: const ReferenceStateScreen(),
    );
  }
}

class ReferenceStateScreen extends StatefulWidget {
  const ReferenceStateScreen({super.key});

  @override
  State<ReferenceStateScreen> createState() => _ReferenceStateScreenState();
}

class _ReferenceStateScreenState extends State<ReferenceStateScreen> {
  double rollDeg = 0;
  double pitchDeg = 0;
  double yawDeg = 0;
  int sequence = 0;

  @override
  Widget build(BuildContext context) {
    final q = quaternionFromEulerDegRpy(rollDeg, pitchDeg, yawDeg);
    final payload = referenceStateMessage(
      sequence: sequence,
      quaternionWxyz: q,
      eulerDegRpy: [rollDeg, pitchDeg, yawDeg],
    );
    final prettyJson = const JsonEncoder.withIndent('  ').convert(payload);

    return Scaffold(
      appBar: AppBar(title: const Text('ESKF Reference')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _AngleSlider(
            label: 'Roll',
            value: rollDeg,
            onChanged: (value) => setState(() => rollDeg = value),
          ),
          _AngleSlider(
            label: 'Pitch',
            value: pitchDeg,
            onChanged: (value) => setState(() => pitchDeg = value),
          ),
          _AngleSlider(
            label: 'Yaw',
            value: yawDeg,
            onChanged: (value) => setState(() => yawDeg = value),
          ),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: () => setState(() => sequence++),
            icon: const Icon(Icons.play_arrow),
            label: const Text('Sample erzeugen'),
          ),
          const SizedBox(height: 20),
          _Readout(label: 'Sequence', value: '$sequence'),
          _Readout(label: 'Euler deg rpy', value: vectorText([rollDeg, pitchDeg, yawDeg], digits: 1)),
          _Readout(label: 'Quaternion wxyz', value: vectorText(q, digits: 5)),
          const SizedBox(height: 20),
          SelectableText(
            prettyJson,
            style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
          ),
        ],
      ),
    );
  }
}

class _AngleSlider extends StatelessWidget {
  const _AngleSlider({
    required this.label,
    required this.value,
    required this.onChanged,
  });

  final String label;
  final double value;
  final ValueChanged<double> onChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('$label: ${value.toStringAsFixed(1)} deg'),
        Slider(
          min: -180,
          max: 180,
          value: value,
          onChanged: onChanged,
        ),
      ],
    );
  }
}

class _Readout extends StatelessWidget {
  const _Readout({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 140, child: Text(label)),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(fontFamily: 'monospace'),
            ),
          ),
        ],
      ),
    );
  }
}

Map<String, Object?> referenceStateMessage({
  required int sequence,
  required List<double> quaternionWxyz,
  required List<double> eulerDegRpy,
}) {
  return {
    'schema_version': '1.0',
    'message_type': 'REFERENCE_STATE',
    'source': 'IPHONE',
    'device_time_s': DateTime.now().microsecondsSinceEpoch / 1000000.0,
    'sequence': sequence,
    'payload': {
      'state_source': 'FlutterManualOrientation',
      'position_available': false,
      'velocity_available': false,
      'position_m': [0, 0, 0],
      'velocity_mps': [0, 0, 0],
      'quaternion_wxyz': quaternionWxyz,
      'euler_deg_rpy': eulerDegRpy,
      'tracking_state': 'manual',
    },
  };
}

List<double> quaternionFromEulerDegRpy(double rollDeg, double pitchDeg, double yawDeg) {
  final roll = rollDeg * math.pi / 180.0;
  final pitch = pitchDeg * math.pi / 180.0;
  final yaw = yawDeg * math.pi / 180.0;

  final cr = math.cos(roll * 0.5);
  final sr = math.sin(roll * 0.5);
  final cp = math.cos(pitch * 0.5);
  final sp = math.sin(pitch * 0.5);
  final cy = math.cos(yaw * 0.5);
  final sy = math.sin(yaw * 0.5);

  final q = [
    cr * cp * cy + sr * sp * sy,
    sr * cp * cy - cr * sp * sy,
    cr * sp * cy + sr * cp * sy,
    cr * cp * sy - sr * sp * cy,
  ];
  final norm = math.sqrt(q.fold<double>(0, (sum, value) => sum + value * value));
  return q.map((value) => value / norm).toList(growable: false);
}

String vectorText(List<double> values, {required int digits}) {
  return '[${values.map((value) => value.toStringAsFixed(digits)).join(', ')}]';
}
