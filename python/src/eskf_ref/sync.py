from __future__ import annotations

from math import sqrt
from typing import Iterable, Sequence


Sample = tuple[float, float]


def gyro_norm_from_messages(messages: Iterable[object], source: str) -> list[Sample]:
    samples: list[Sample] = []
    for msg in messages:
        if getattr(msg, "message_type", None) != "RAW_SENSOR":
            continue
        if getattr(msg, "source", None) != source:
            continue
        payload = getattr(msg, "payload")
        gyro = payload.get("gyro_radps") or payload.get("rotation_rate_radps")
        if not gyro or len(gyro) != 3:
            continue
        wx, wy, wz = (float(item) for item in gyro)
        samples.append((float(getattr(msg, "device_time_s")), sqrt(wx * wx + wy * wy + wz * wz)))
    return sorted(samples)


def interpolate(samples: Sequence[Sample], t: float) -> float | None:
    if not samples or t < samples[0][0] or t > samples[-1][0]:
        return None
    lo = 0
    hi = len(samples) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if samples[mid][0] <= t:
            lo = mid
        else:
            hi = mid
    t0, y0 = samples[lo]
    t1, y1 = samples[hi]
    if t1 == t0:
        return y0
    f = (t - t0) / (t1 - t0)
    return y0 + f * (y1 - y0)


def pearson(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b) or len(a) < 2:
        return float("nan")
    mean_a = sum(a) / len(a)
    mean_b = sum(b) / len(b)
    da = [item - mean_a for item in a]
    db = [item - mean_b for item in b]
    denom = sqrt(sum(item * item for item in da) * sum(item * item for item in db))
    if denom == 0:
        return float("nan")
    return sum(x * y for x, y in zip(da, db)) / denom


def estimate_time_offset_s(
    reference: Sequence[Sample],
    moving: Sequence[Sample],
    *,
    max_lag_s: float = 2.0,
    step_s: float = 0.005,
    sample_period_s: float = 0.01,
) -> tuple[float, float]:
    """Return offset so that moving(t + offset) best aligns with reference(t)."""
    if len(reference) < 3 or len(moving) < 3:
        raise ValueError("need at least 3 samples for each signal")

    start_t = max(reference[0][0], moving[0][0] - max_lag_s)
    end_t = min(reference[-1][0], moving[-1][0] + max_lag_s)
    if end_t <= start_t:
        raise ValueError("signals do not overlap")

    best_offset = 0.0
    best_corr = -2.0
    lag_count = int((2.0 * max_lag_s) / step_s) + 1

    for index in range(lag_count):
        offset = -max_lag_s + index * step_s
        ref_values: list[float] = []
        moving_values: list[float] = []
        t = start_t
        while t <= end_t:
            ref_y = interpolate(reference, t)
            moving_y = interpolate(moving, t + offset)
            if ref_y is not None and moving_y is not None:
                ref_values.append(ref_y)
                moving_values.append(moving_y)
            t += sample_period_s
        corr = pearson(ref_values, moving_values)
        if corr == corr and corr > best_corr:
            best_corr = corr
            best_offset = offset

    return best_offset, best_corr
