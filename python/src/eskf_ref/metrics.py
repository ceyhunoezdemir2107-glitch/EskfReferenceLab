from __future__ import annotations

from math import acos, sqrt
from typing import Iterable, Sequence


Vector3 = Sequence[float]
Quaternion = Sequence[float]  # [w, x, y, z]


def rmse(errors: Iterable[float]) -> float:
    values = list(errors)
    if not values:
        return float("nan")
    return sqrt(sum(value * value for value in values) / len(values))


def vector_error_norm(a: Vector3, b: Vector3) -> float:
    if len(a) != len(b):
        raise ValueError("vectors must have the same length")
    return sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def quat_normalize(q: Quaternion) -> tuple[float, float, float, float]:
    if len(q) != 4:
        raise ValueError("quaternion must have 4 elements [w, x, y, z]")
    w, x, y, z = (float(item) for item in q)
    norm = sqrt(w * w + x * x + y * y + z * z)
    if norm == 0:
        raise ValueError("zero quaternion")
    return (w / norm, x / norm, y / norm, z / norm)


def quat_conjugate(q: Quaternion) -> tuple[float, float, float, float]:
    w, x, y, z = quat_normalize(q)
    return (w, -x, -y, -z)


def quat_multiply(a: Quaternion, b: Quaternion) -> tuple[float, float, float, float]:
    aw, ax, ay, az = quat_normalize(a)
    bw, bx, by, bz = quat_normalize(b)
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def orientation_error_rad(q_ref: Quaternion, q_est: Quaternion) -> float:
    q_error = quat_multiply(quat_conjugate(q_ref), q_est)
    w = abs(quat_normalize(q_error)[0])
    w = min(1.0, max(-1.0, w))
    return 2.0 * acos(w)


def pair_state_messages(messages: Sequence[object], max_dt_s: float = 0.02) -> list[tuple[object, object]]:
    refs = [
        item for item in messages
        if getattr(item, "message_type", None) == "REFERENCE_STATE"
    ]
    ests = [
        item for item in messages
        if getattr(item, "message_type", None) == "ESTIMATOR_STATE"
    ]

    pairs: list[tuple[object, object]] = []
    start_index = 0
    for ref in refs:
        ref_t = float(getattr(ref, "device_time_s"))
        best_index = None
        best_dt = max_dt_s
        for index in range(start_index, len(ests)):
            est_t = float(getattr(ests[index], "device_time_s"))
            dt = abs(est_t - ref_t)
            if dt <= best_dt:
                best_dt = dt
                best_index = index
            if est_t > ref_t + max_dt_s:
                break
        if best_index is not None:
            pairs.append((ref, ests[best_index]))
            start_index = best_index
    return pairs


def compute_state_metrics(pairs: Sequence[tuple[object, object]]) -> dict[str, float]:
    position_errors: list[float] = []
    velocity_errors: list[float] = []
    orientation_errors: list[float] = []

    for ref, est in pairs:
        ref_payload = getattr(ref, "payload")
        est_payload = getattr(est, "payload")
        if "position_m" in ref_payload and "position_m" in est_payload:
            position_errors.append(vector_error_norm(est_payload["position_m"], ref_payload["position_m"]))
        if "velocity_mps" in ref_payload and "velocity_mps" in est_payload:
            velocity_errors.append(vector_error_norm(est_payload["velocity_mps"], ref_payload["velocity_mps"]))
        if "quaternion_wxyz" in ref_payload and "quaternion_wxyz" in est_payload:
            orientation_errors.append(
                orientation_error_rad(ref_payload["quaternion_wxyz"], est_payload["quaternion_wxyz"])
            )

    return {
        "pair_count": float(len(pairs)),
        "position_rmse_m": rmse(position_errors),
        "velocity_rmse_mps": rmse(velocity_errors),
        "orientation_rmse_rad": rmse(orientation_errors),
        "orientation_rmse_deg": rmse(orientation_errors) * 180.0 / 3.141592653589793,
        "position_max_m": max(position_errors) if position_errors else float("nan"),
        "velocity_max_mps": max(velocity_errors) if velocity_errors else float("nan"),
        "orientation_max_rad": max(orientation_errors) if orientation_errors else float("nan"),
    }
