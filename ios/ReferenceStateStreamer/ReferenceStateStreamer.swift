import ARKit
import CoreMotion
import Foundation
import simd

@MainActor
final class ReferenceStateStreamer: NSObject, ObservableObject, ARSessionDelegate {
    @Published var isRunning = false
    @Published var sequence: UInt64 = 0
    @Published var trackingState = "stopped"
    @Published var orientationSummary = "Roll -, Pitch -, Yaw -"
    @Published var quaternionSummary = "Quaternion wxyz: -"
    @Published var lastError = "-"

    private let session = ARSession()
    private let motionManager = CMMotionManager()
    private let udp = UdpClient()
    private var lastPose: (time: TimeInterval, position: SIMD3<Float>)?
    private var velocityEstimate = SIMD3<Float>(repeating: 0)

    override init() {
        super.init()
        session.delegate = self
    }

    func start(host: String, port: UInt16) {
        guard ARWorldTrackingConfiguration.isSupported else {
            lastError = "ARWorldTracking not supported"
            return
        }

        udp.connect(host: host, port: port)

        let config = ARWorldTrackingConfiguration()
        config.worldAlignment = .gravity
        session.run(config, options: [.resetTracking, .removeExistingAnchors])

        startRawMotion()
        isRunning = true
        lastError = "-"
    }

    func stop() {
        session.pause()
        motionManager.stopGyroUpdates()
        motionManager.stopAccelerometerUpdates()
        udp.close()
        isRunning = false
        trackingState = "stopped"
    }

    nonisolated func session(_ session: ARSession, didUpdate frame: ARFrame) {
        Task { @MainActor in
            self.sendReferenceState(frame: frame)
        }
    }

    private func sendReferenceState(frame: ARFrame) {
        let transform = frame.camera.transform
        let position = SIMD3<Float>(
            transform.columns.3.x,
            transform.columns.3.y,
            transform.columns.3.z
        )
        let quaternion = simd_quatf(transform)
        let eulerDegRpy = eulerDegRpy(from: quaternion)
        let now = frame.timestamp
        velocityEstimate = estimateVelocity(time: now, position: position)
        trackingState = trackingDescription(frame.camera.trackingState)
        orientationSummary = String(
            format: "Roll %.1f deg, Pitch %.1f deg, Yaw %.1f deg",
            eulerDegRpy[0],
            eulerDegRpy[1],
            eulerDegRpy[2]
        )
        quaternionSummary = String(
            format: "Quaternion wxyz: [%.4f, %.4f, %.4f, %.4f]",
            quaternion.real,
            quaternion.imag.x,
            quaternion.imag.y,
            quaternion.imag.z
        )

        let payload: [String: Any] = [
            "state_source": "ARKit",
            "position_m": [Double(position.x), Double(position.y), Double(position.z)],
            "velocity_mps": [Double(velocityEstimate.x), Double(velocityEstimate.y), Double(velocityEstimate.z)],
            "quaternion_wxyz": [
                Double(quaternion.real),
                Double(quaternion.imag.x),
                Double(quaternion.imag.y),
                Double(quaternion.imag.z)
            ],
            "euler_deg_rpy": [
                Double(eulerDegRpy[0]),
                Double(eulerDegRpy[1]),
                Double(eulerDegRpy[2])
            ],
            "tracking_state": trackingState
        ]
        sendMessage(type: "REFERENCE_STATE", deviceTime: now, payload: payload)
    }

    private func eulerDegRpy(from quaternion: simd_quatf) -> [Double] {
        var w = Double(quaternion.real)
        var x = Double(quaternion.imag.x)
        var y = Double(quaternion.imag.y)
        var z = Double(quaternion.imag.z)
        let norm = sqrt(w * w + x * x + y * y + z * z)
        if norm > 0 {
            w /= norm
            x /= norm
            y /= norm
            z /= norm
        }

        let roll = atan2(
            2.0 * (w * x + y * z),
            1.0 - 2.0 * (x * x + y * y)
        )
        let pitchArg = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
        let pitch = asin(pitchArg)
        let yaw = atan2(
            2.0 * (w * z + x * y),
            1.0 - 2.0 * (y * y + z * z)
        )

        return [
            roll * 180.0 / .pi,
            pitch * 180.0 / .pi,
            yaw * 180.0 / .pi
        ]
    }

    private func startRawMotion() {
        if motionManager.isGyroAvailable {
            motionManager.gyroUpdateInterval = 1.0 / 100.0
            motionManager.startGyroUpdates(to: .main) { [weak self] data, _ in
                guard let self, let data else { return }
                let payload: [String: Any] = [
                    "gyro_radps": [
                        data.rotationRate.x,
                        data.rotationRate.y,
                        data.rotationRate.z
                    ]
                ]
                self.sendMessage(type: "RAW_SENSOR", deviceTime: data.timestamp, payload: payload)
            }
        }

        if motionManager.isAccelerometerAvailable {
            motionManager.accelerometerUpdateInterval = 1.0 / 100.0
            motionManager.startAccelerometerUpdates(to: .main) { [weak self] data, _ in
                guard let self, let data else { return }
                let payload: [String: Any] = [
                    "accel_mps2": [
                        data.acceleration.x * 9.80665,
                        data.acceleration.y * 9.80665,
                        data.acceleration.z * 9.80665
                    ]
                ]
                self.sendMessage(type: "RAW_SENSOR", deviceTime: data.timestamp, payload: payload)
            }
        }
    }

    private func estimateVelocity(time: TimeInterval, position: SIMD3<Float>) -> SIMD3<Float> {
        defer {
            lastPose = (time, position)
        }
        guard let lastPose else {
            return SIMD3<Float>(repeating: 0)
        }
        let dt = Float(time - lastPose.time)
        guard dt > 0.001 else {
            return velocityEstimate
        }
        let raw = (position - lastPose.position) / dt
        return 0.75 * velocityEstimate + 0.25 * raw
    }

    private func sendMessage(type: String, deviceTime: TimeInterval, payload: [String: Any]) {
        let message: [String: Any] = [
            "schema_version": "1.0",
            "message_type": type,
            "source": "IPHONE",
            "device_time_s": deviceTime,
            "sequence": sequence,
            "payload": payload
        ]
        sequence += 1

        do {
            let data = try JSONSerialization.data(withJSONObject: message, options: [])
            udp.send(data)
        } catch {
            lastError = error.localizedDescription
        }
    }

    private func trackingDescription(_ state: ARCamera.TrackingState) -> String {
        switch state {
        case .normal:
            return "normal"
        case .notAvailable:
            return "not_available"
        case .limited(let reason):
            switch reason {
            case .initializing:
                return "limited_initializing"
            case .excessiveMotion:
                return "limited_excessive_motion"
            case .insufficientFeatures:
                return "limited_insufficient_features"
            case .relocalizing:
                return "limited_relocalizing"
            @unknown default:
                return "limited_unknown"
            }
        }
    }
}
