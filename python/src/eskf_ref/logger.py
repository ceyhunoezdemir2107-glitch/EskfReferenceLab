from __future__ import annotations

import gzip
import socket
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from .messages import LogEnvelope, parse_message


@dataclass
class TransferStats:
    start_time_s: float = field(default_factory=time.monotonic)
    messages: int = 0
    bytes_received: int = 0
    parse_errors: int = 0
    receive_errors: int = 0
    sequence_gaps: int = 0
    _last_sequence_by_source: dict[str, int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record_message(self, envelope: LogEnvelope, byte_count: int) -> None:
        with self._lock:
            self.messages += 1
            self.bytes_received += byte_count
            if envelope.sequence is None:
                return
            last_sequence = self._last_sequence_by_source.get(envelope.source)
            if last_sequence is not None and envelope.sequence > last_sequence + 1:
                self.sequence_gaps += envelope.sequence - last_sequence - 1
            self._last_sequence_by_source[envelope.source] = envelope.sequence

    def record_parse_error(self) -> None:
        with self._lock:
            self.parse_errors += 1

    def record_receive_error(self) -> None:
        with self._lock:
            self.receive_errors += 1

    def snapshot(self) -> dict[str, float | int]:
        with self._lock:
            elapsed_s = max(time.monotonic() - self.start_time_s, 1e-9)
            return {
                "elapsed_s": elapsed_s,
                "messages": self.messages,
                "bytes_received": self.bytes_received,
                "parse_errors": self.parse_errors,
                "receive_errors": self.receive_errors,
                "sequence_gaps": self.sequence_gaps,
            }


class JsonlWriter:
    def __init__(self, path: str, *, flush_interval_s: float = 2.0):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.flush_interval_s = flush_interval_s
        self._lock = threading.Lock()
        self._handle: TextIO | None = None
        self._last_flush_s = time.monotonic()

    def __enter__(self) -> "JsonlWriter":
        if self.path.suffix == ".gz":
            self._handle = gzip.open(self.path, "at", encoding="utf-8", compresslevel=1)
        else:
            self._handle = self.path.open("a", encoding="utf-8", buffering=1024 * 1024)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._handle is not None:
            self._handle.flush()
            self._handle.close()

    def write_raw(self, raw: bytes | str, transport: str) -> LogEnvelope:
        if self._handle is None:
            raise RuntimeError("writer is not open")
        envelope = parse_message(raw, pc_recv_time_s=time.monotonic(), transport=transport)
        with self._lock:
            self._handle.write(envelope.to_json_line())
            self._handle.write("\n")
            now_s = time.monotonic()
            if now_s - self._last_flush_s >= self.flush_interval_s:
                self._handle.flush()
                self._last_flush_s = now_s
        return envelope

    def flush(self) -> None:
        if self._handle is None:
            return
        with self._lock:
            self._handle.flush()


class UdpReceiver(threading.Thread):
    def __init__(
        self,
        host: str,
        port: int,
        writer: JsonlWriter,
        stop_event: threading.Event,
        stats: TransferStats,
        recv_buffer_bytes: int,
    ):
        super().__init__(name="udp-receiver", daemon=True)
        self.host = host
        self.port = port
        self.writer = writer
        self.stop_event = stop_event
        self.stats = stats
        self.recv_buffer_bytes = recv_buffer_bytes
        self.errors = 0

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.recv_buffer_bytes)
        sock.settimeout(0.5)
        sock.bind((self.host, self.port))
        try:
            while not self.stop_event.is_set():
                try:
                    payload, _addr = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                try:
                    envelope = self.writer.write_raw(payload, "udp")
                    self.stats.record_message(envelope, len(payload))
                except Exception:
                    self.errors += 1
                    self.stats.record_parse_error()
        finally:
            sock.close()


class SerialReceiver(threading.Thread):
    def __init__(self, port: str, baud: int, writer: JsonlWriter, stop_event: threading.Event, stats: TransferStats):
        super().__init__(name="serial-receiver", daemon=True)
        self.port = port
        self.baud = baud
        self.writer = writer
        self.stop_event = stop_event
        self.stats = stats
        self.errors = 0

    def run(self) -> None:
        import serial

        with serial.Serial(self.port, self.baud, timeout=0.5) as ser:
            while not self.stop_event.is_set():
                line = ser.readline()
                if not line:
                    continue
                try:
                    envelope = self.writer.write_raw(line, "serial")
                    self.stats.record_message(envelope, len(line))
                except Exception:
                    self.errors += 1
                    self.stats.record_parse_error()


class StatsReporter(threading.Thread):
    def __init__(self, stats: TransferStats, stop_event: threading.Event, interval_s: float):
        super().__init__(name="stats-reporter", daemon=True)
        self.stats = stats
        self.stop_event = stop_event
        self.interval_s = interval_s

    def run(self) -> None:
        previous = self.stats.snapshot()
        while not self.stop_event.wait(self.interval_s):
            current = self.stats.snapshot()
            dt_s = max(float(current["elapsed_s"]) - float(previous["elapsed_s"]), 1e-9)
            delta_messages = int(current["messages"]) - int(previous["messages"])
            delta_bytes = int(current["bytes_received"]) - int(previous["bytes_received"])
            messages_per_s = delta_messages / dt_s
            mb_per_s = delta_bytes / dt_s / 1_000_000
            total_mb = int(current["bytes_received"]) / 1_000_000
            print(
                "RX "
                f"{messages_per_s:7.1f} msg/s "
                f"{mb_per_s:6.3f} MB/s "
                f"total={int(current['messages'])} "
                f"{total_mb:.2f} MB "
                f"gaps={int(current['sequence_gaps'])} "
                f"errors={int(current['parse_errors']) + int(current['receive_errors'])}",
                flush=True,
            )
            previous = current


def run_logger(
    *,
    out_path: str,
    udp_host: str = "0.0.0.0",
    udp_port: int | None = 5555,
    serial_port: str | None = None,
    serial_baud: int = 115200,
    status_interval_s: float = 2.0,
    udp_recv_buffer_bytes: int = 4 * 1024 * 1024,
) -> None:
    stop_event = threading.Event()
    threads: list[threading.Thread] = []
    stats = TransferStats()

    with JsonlWriter(out_path) as writer:
        if udp_port is not None:
            threads.append(UdpReceiver(udp_host, udp_port, writer, stop_event, stats, udp_recv_buffer_bytes))
        if serial_port:
            threads.append(SerialReceiver(serial_port, serial_baud, writer, stop_event, stats))

        if not threads:
            raise ValueError("enable at least one input: UDP or serial")

        if status_interval_s > 0:
            threads.append(StatsReporter(stats, stop_event, status_interval_s))

        print(f"Writing messages to {Path(out_path)}")
        if udp_port is not None:
            print(f"Listening for UDP on {udp_host}:{udp_port}")
        for thread in threads:
            thread.start()

        try:
            while any(thread.is_alive() for thread in threads):
                time.sleep(0.5)
        except KeyboardInterrupt:
            stop_event.set()
            for thread in threads:
                thread.join(timeout=2.0)
        finally:
            stop_event.set()
            writer.flush()
            snapshot = stats.snapshot()
            elapsed_s = float(snapshot["elapsed_s"])
            mb_total = int(snapshot["bytes_received"]) / 1_000_000
            print(
                "Stopped. "
                f"messages={int(snapshot['messages'])}, "
                f"received={mb_total:.2f} MB, "
                f"duration={elapsed_s:.1f} s, "
                f"sequence_gaps={int(snapshot['sequence_gaps'])}, "
                f"errors={int(snapshot['parse_errors']) + int(snapshot['receive_errors'])}"
            )
