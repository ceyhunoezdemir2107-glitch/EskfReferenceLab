from __future__ import annotations

import gzip
import os
from collections import Counter
from pathlib import Path

from .messages import iter_jsonl, open_text_log


def estimate_uncompressed_bytes(path: str) -> int:
    total = 0
    with open_text_log(path) as handle:
        for line in handle:
            total += len(line.encode("utf-8"))
    return total


def compressed_size_bytes(path: str) -> int | None:
    if Path(path).suffix != ".gz":
        return None
    return os.path.getsize(path)


def summarize_log(path: str) -> dict[str, object]:
    count_by_type: Counter[str] = Counter()
    count_by_source: Counter[str] = Counter()
    count_by_payload_kind: Counter[str] = Counter()
    first_t: float | None = None
    last_t: float | None = None
    message_count = 0

    for _line_number, message in iter_jsonl(path):
        message_count += 1
        count_by_type[message.message_type] += 1
        count_by_source[message.source] += 1
        if "gyro_radps" in message.payload:
            count_by_payload_kind["gyro"] += 1
        if "accel_mps2" in message.payload:
            count_by_payload_kind["accel"] += 1
        if "latitude_deg" in message.payload:
            count_by_payload_kind["location"] += 1
        if "altitude_m" in message.payload:
            count_by_payload_kind["altitude"] += 1
        if "speed_mps" in message.payload:
            count_by_payload_kind["speed"] += 1
        if "quaternion_wxyz" in message.payload:
            count_by_payload_kind["orientation"] += 1
        first_t = message.device_time_s if first_t is None else min(first_t, message.device_time_s)
        last_t = message.device_time_s if last_t is None else max(last_t, message.device_time_s)

    duration_s = max(0.0, (last_t - first_t) if first_t is not None and last_t is not None else 0.0)
    uncompressed = estimate_uncompressed_bytes(path)
    compressed = compressed_size_bytes(path)
    effective_size = compressed if compressed is not None else uncompressed
    duration_h = duration_s / 3600.0 if duration_s > 0 else 0.0
    messages_per_s = message_count / duration_s if duration_s > 0 else None
    estimated_mb_per_hour = (effective_size / 1_000_000.0 / duration_h) if duration_h > 0 else None

    return {
        "path": path,
        "message_count": message_count,
        "duration_s": duration_s,
        "messages_per_s": messages_per_s,
        "uncompressed_mb": uncompressed / 1_000_000.0,
        "compressed_mb": compressed / 1_000_000.0 if compressed is not None else None,
        "compression_ratio": (uncompressed / compressed) if compressed else None,
        "estimated_mb_per_hour": estimated_mb_per_hour,
        "count_by_type": dict(count_by_type),
        "count_by_source": dict(count_by_source),
        "count_by_payload_kind": dict(count_by_payload_kind),
    }
