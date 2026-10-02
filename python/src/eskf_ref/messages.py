from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TextIO


SCHEMA_VERSION = "1.0"


class MessageType(str, Enum):
    REFERENCE_STATE = "REFERENCE_STATE"
    ESTIMATOR_STATE = "ESTIMATOR_STATE"
    TELEMETRY_SUMMARY = "TELEMETRY_SUMMARY"
    RAW_SENSOR = "RAW_SENSOR"
    FILTER_DIAGNOSTIC = "FILTER_DIAGNOSTIC"
    CLOCK_SYNC = "CLOCK_SYNC"


class Source(str, Enum):
    IPHONE = "IPHONE"
    ANDROID = "ANDROID"
    WEB = "WEB"
    ARDUINO = "ARDUINO"
    PC = "PC"


@dataclass(frozen=True)
class LogEnvelope:
    schema_version: str
    message_type: str
    source: str
    device_time_s: float
    sequence: int | None
    payload: dict[str, Any]
    pc_recv_time_s: float | None = None
    transport: str | None = None

    def to_json_line(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), sort_keys=True)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "message_type": self.message_type,
            "source": self.source,
            "device_time_s": self.device_time_s,
            "payload": self.payload,
        }
        if self.sequence is not None:
            result["sequence"] = self.sequence
        if self.pc_recv_time_s is not None:
            result["pc_recv_time_s"] = self.pc_recv_time_s
        if self.transport is not None:
            result["transport"] = self.transport
        return result


def parse_message(raw: bytes | str, *, pc_recv_time_s: float | None = None, transport: str | None = None) -> LogEnvelope:
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    data = json.loads(text)

    missing = [key for key in ("message_type", "source", "device_time_s", "payload") if key not in data]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")

    message_type = str(data["message_type"])
    source = str(data["source"])
    if message_type not in {item.value for item in MessageType}:
        raise ValueError(f"unsupported message_type: {message_type}")
    if source not in {item.value for item in Source}:
        raise ValueError(f"unsupported source: {source}")

    payload = data["payload"]
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    return LogEnvelope(
        schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
        message_type=message_type,
        source=source,
        device_time_s=float(data["device_time_s"]),
        sequence=int(data["sequence"]) if "sequence" in data and data["sequence"] is not None else None,
        payload=payload,
        pc_recv_time_s=pc_recv_time_s,
        transport=transport,
    )


def load_jsonl(path: str) -> list[LogEnvelope]:
    messages: list[LogEnvelope] = []
    for _line_number, message in iter_jsonl(path):
        messages.append(message)
    return messages


def open_text_log(path: str) -> TextIO:
    opener = gzip.open if Path(path).suffix == ".gz" else open
    return opener(path, "rt", encoding="utf-8")


def iter_jsonl(path: str):
    with open_text_log(path) as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield line_number, parse_message(stripped)
            except Exception as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc
