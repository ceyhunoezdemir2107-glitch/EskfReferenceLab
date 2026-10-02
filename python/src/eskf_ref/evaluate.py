from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .messages import LogEnvelope, load_jsonl
from .metrics import orientation_error_rad, quat_multiply, quat_conjugate, quat_normalize, rmse, vector_error_norm
from .sync import estimate_time_offset_s, gyro_norm_from_messages


@dataclass(frozen=True)
class TimedMessage:
    message: LogEnvelope
    time_s: float


def evaluate_log(
    path: str,
    *,
    reference_source: str,
    estimator_source: str,
    max_dt_s: float = 0.05,
    time_offset_s: float = 0.0,
    sync_from_gyro: bool = False,
    sync_max_lag_s: float = 2.0,
    csv_out: str | None = None,
    plots_dir: str | None = None,
) -> dict[str, Any]:
    messages = load_jsonl(path)
    sync: dict[str, Any] | None = None
    applied_offset_s = time_offset_s

    if sync_from_gyro:
        reference_gyro = gyro_norm_from_messages(messages, reference_source)
        estimator_gyro = gyro_norm_from_messages(messages, estimator_source)
        applied_offset_s, corr = estimate_time_offset_s(
            reference_gyro,
            estimator_gyro,
            max_lag_s=sync_max_lag_s,
        )
        sync = {
            "method": "gyro_cross_correlation",
            "moving_source": estimator_source,
            "reference_source": reference_source,
            "moving_time_offset_s": applied_offset_s,
            "correlation": corr,
            "reference_gyro_samples": len(reference_gyro),
            "moving_gyro_samples": len(estimator_gyro),
        }

    reference_states = _state_messages(messages, "REFERENCE_STATE", reference_source, 0.0)
    estimator_states = _state_messages(messages, "ESTIMATOR_STATE", estimator_source, applied_offset_s)
    pairs = _pair_nearest(reference_states, estimator_states, max_dt_s=max_dt_s)
    rows = [_error_row(ref, est) for ref, est in pairs]

    if csv_out:
        _write_csv(csv_out, rows)
    if plots_dir:
        _write_plots(plots_dir, rows)

    return {
        "input": path,
        "reference_source": reference_source,
        "estimator_source": estimator_source,
        "max_pair_dt_s": max_dt_s,
        "applied_estimator_time_offset_s": applied_offset_s,
        "sync": sync,
        "message_counts": _message_counts(messages),
        "reference_state_count": len(reference_states),
        "estimator_state_count": len(estimator_states),
        "pair_count": len(rows),
        "metrics": _metrics_from_rows(rows),
        "outputs": {
            "csv": csv_out,
            "plots_dir": plots_dir,
        },
        "notes": _notes(reference_states, estimator_states, rows),
    }


def _state_messages(messages: Sequence[LogEnvelope], message_type: str, source: str, time_offset_s: float) -> list[TimedMessage]:
    result: list[TimedMessage] = []
    for message in messages:
        if message.message_type != message_type or message.source != source:
            continue
        # estimate_time_offset_s returns offset such that moving(t + offset) aligns
        # with reference(t), so subtract it to express moving samples in reference time.
        result.append(TimedMessage(message, message.device_time_s - time_offset_s))
    return sorted(result, key=lambda item: item.time_s)


def _pair_nearest(
    references: Sequence[TimedMessage],
    estimators: Sequence[TimedMessage],
    *,
    max_dt_s: float,
) -> list[tuple[TimedMessage, TimedMessage]]:
    pairs: list[tuple[TimedMessage, TimedMessage]] = []
    start_index = 0
    for reference in references:
        best_index = None
        best_dt = max_dt_s
        for index in range(start_index, len(estimators)):
            estimator = estimators[index]
            dt = abs(estimator.time_s - reference.time_s)
            if dt <= best_dt:
                best_dt = dt
                best_index = index
            if estimator.time_s > reference.time_s + max_dt_s:
                break
        if best_index is not None:
            pairs.append((reference, estimators[best_index]))
            start_index = best_index
    return pairs


def _error_row(reference: TimedMessage, estimator: TimedMessage) -> dict[str, Any]:
    ref_payload = reference.message.payload
    est_payload = estimator.message.payload
    row: dict[str, Any] = {
        "t_ref_s": reference.time_s,
        "t_est_s": estimator.time_s,
        "dt_s": estimator.time_s - reference.time_s,
    }

    if _vector_available(ref_payload, "position_m", "position_available") and "position_m" in est_payload:
        row["position_error_m"] = vector_error_norm(est_payload["position_m"], ref_payload["position_m"])
        row["vertical_error_m"] = float(est_payload["position_m"][2]) - float(ref_payload["position_m"][2])

    if _vector_available(ref_payload, "velocity_mps", "velocity_available") and "velocity_mps" in est_payload:
        row["velocity_error_mps"] = vector_error_norm(est_payload["velocity_mps"], ref_payload["velocity_mps"])

    if "quaternion_wxyz" in ref_payload and "quaternion_wxyz" in est_payload:
        row["orientation_error_rad"] = orientation_error_rad(ref_payload["quaternion_wxyz"], est_payload["quaternion_wxyz"])
        row["orientation_error_deg"] = math.degrees(row["orientation_error_rad"])
        q_error = quat_multiply(quat_conjugate(ref_payload["quaternion_wxyz"]), est_payload["quaternion_wxyz"])
        yaw, pitch, roll = quat_to_ypr_rad(q_error)
        row["yaw_error_deg"] = math.degrees(_wrap_pi(yaw))
        row["pitch_error_deg"] = math.degrees(_wrap_pi(pitch))
        row["roll_error_deg"] = math.degrees(_wrap_pi(roll))

    for key in ("accel_bias_mps2", "gyro_bias_radps"):
        if key in est_payload:
            row[f"{key}_norm"] = math.sqrt(sum(float(item) ** 2 for item in est_payload[key]))

    return row


def _vector_available(payload: dict[str, Any], vector_key: str, availability_key: str) -> bool:
    return vector_key in payload and payload.get(availability_key, True) is not False


def quat_to_ypr_rad(q: Sequence[float]) -> tuple[float, float, float]:
    w, x, y, z = quat_normalize(q)
    yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    pitch_arg = 2.0 * (w * y - z * x)
    pitch = math.asin(max(-1.0, min(1.0, pitch_arg)))
    roll = math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y))
    return yaw, pitch, roll


def _wrap_pi(angle: float) -> float:
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def _metrics_from_rows(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"pair_count": len(rows)}
    metric_keys = [
        "dt_s",
        "position_error_m",
        "velocity_error_mps",
        "orientation_error_rad",
        "orientation_error_deg",
        "yaw_error_deg",
        "pitch_error_deg",
        "roll_error_deg",
        "vertical_error_m",
        "accel_bias_mps2_norm",
        "gyro_bias_radps_norm",
    ]
    for key in metric_keys:
        values = [float(row[key]) for row in rows if key in row]
        if not values:
            result[f"{key}_count"] = 0
            continue
        result[f"{key}_count"] = len(values)
        result[f"{key}_rmse"] = rmse(values)
        result[f"{key}_mean"] = sum(values) / len(values)
        result[f"{key}_max_abs"] = max(abs(value) for value in values)
        result[f"{key}_final"] = values[-1]
    return result


def _message_counts(messages: Sequence[LogEnvelope]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for message in messages:
        key = f"{message.source}:{message.message_type}"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _notes(
    reference_states: Sequence[TimedMessage],
    estimator_states: Sequence[TimedMessage],
    rows: Sequence[dict[str, Any]],
) -> list[str]:
    notes: list[str] = []
    if not reference_states:
        notes.append("No reference states found for the selected reference source.")
    if not estimator_states:
        notes.append("No estimator states found for the selected estimator source. Add Arduino ESTIMATOR_STATE logs before state-vs-state metrics are available.")
    if reference_states and estimator_states and not rows:
        notes.append("Reference and estimator states were found, but no pairs were within max_pair_dt_s.")
    if rows and not any("position_error_m" in row for row in rows):
        notes.append("No position metrics computed. Reference or estimator position is unavailable.")
    if rows and not any("velocity_error_mps" in row for row in rows):
        notes.append("No velocity metrics computed. Reference or estimator velocity is unavailable.")
    return notes


def _write_csv(path: str, rows: Sequence[dict[str, Any]]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_plots(path: str, rows: Sequence[dict[str, Any]]) -> None:
    output = Path(path)
    output.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib.pyplot as plt
    except Exception:
        (output / "plots_skipped.txt").write_text("matplotlib is not installed.\n", encoding="utf-8")
        return

    plot_specs = [
        ("position_error_m", "Position Error [m]", "position_error.png"),
        ("velocity_error_mps", "Velocity Error [m/s]", "velocity_error.png"),
        ("orientation_error_deg", "Orientation Error [deg]", "orientation_error.png"),
        ("yaw_error_deg", "Yaw Error [deg]", "yaw_error.png"),
    ]
    t0 = rows[0]["t_ref_s"] if rows else 0.0
    for key, ylabel, file_name in plot_specs:
        plot_rows = [row for row in rows if key in row]
        if not plot_rows:
            continue
        xs = [row["t_ref_s"] - t0 for row in plot_rows]
        ys = [row[key] for row in plot_rows]
        plt.figure()
        plt.plot(xs, ys)
        plt.xlabel("time [s]")
        plt.ylabel(ylabel)
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(output / file_name)
        plt.close()
