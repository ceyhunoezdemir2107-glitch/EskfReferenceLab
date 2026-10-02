from __future__ import annotations

import argparse
import json

from .evaluate import evaluate_log
from .file_receiver import run_file_receiver
from .logger import run_logger
from .log_stats import summarize_log
from .messages import Source, load_jsonl
from .metrics import compute_state_metrics, pair_state_messages
from .sync import estimate_time_offset_s, gyro_norm_from_messages
from .web_server import run_web_server


def _cmd_log(args: argparse.Namespace) -> None:
    run_logger(
        out_path=args.out,
        udp_host=args.udp_host,
        udp_port=args.udp_port,
        serial_port=args.serial,
        serial_baud=args.baud,
        status_interval_s=args.status_interval_s,
        udp_recv_buffer_bytes=args.udp_recv_buffer_mb * 1024 * 1024,
    )


def _cmd_analyze(args: argparse.Namespace) -> None:
    messages = load_jsonl(args.input)
    pairs = pair_state_messages(messages, max_dt_s=args.max_dt_s)
    metrics = compute_state_metrics(pairs)
    print(json.dumps(metrics, indent=2, sort_keys=True))


def _cmd_sync(args: argparse.Namespace) -> None:
    messages = load_jsonl(args.input)
    reference = gyro_norm_from_messages(messages, args.reference_source)
    moving = gyro_norm_from_messages(messages, args.moving_source)
    offset_s, corr = estimate_time_offset_s(
        reference,
        moving,
        max_lag_s=args.max_lag_s,
        step_s=args.step_s,
        sample_period_s=args.sample_period_s,
    )
    print(json.dumps({
        "reference_source": args.reference_source,
        "moving_source": args.moving_source,
        "moving_time_offset_s": offset_s,
        "correlation": corr,
    }, indent=2))


def _cmd_web(args: argparse.Namespace) -> None:
    run_web_server(args.host, args.port, args.out, args.static_dir)


def _cmd_receive_file(args: argparse.Namespace) -> None:
    run_file_receiver(args.host, args.port, args.out_dir)


def _cmd_stats(args: argparse.Namespace) -> None:
    print(json.dumps(summarize_log(args.input), indent=2, sort_keys=True))


def _cmd_evaluate(args: argparse.Namespace) -> None:
    result = evaluate_log(
        args.input,
        reference_source=args.reference_source,
        estimator_source=args.estimator_source,
        max_dt_s=args.max_dt_s,
        time_offset_s=args.time_offset_s,
        sync_from_gyro=args.sync_from_gyro,
        sync_max_lag_s=args.sync_max_lag_s,
        csv_out=args.csv_out,
        plots_dir=args.plots_dir,
    )
    if args.summary_out:
        with open(args.summary_out, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
    print(json.dumps(result, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eskf-ref")
    sub = parser.add_subparsers(required=True)

    log_parser = sub.add_parser("log", help="record UDP and/or serial JSON messages to JSONL")
    log_parser.add_argument("--out", required=True, help="output JSONL path")
    log_parser.add_argument("--udp-host", default="0.0.0.0")
    log_parser.add_argument("--udp-port", type=int, default=5555)
    log_parser.add_argument("--udp-recv-buffer-mb", type=int, default=4)
    log_parser.add_argument("--status-interval-s", type=float, default=2.0)
    log_parser.add_argument("--serial", help="serial port, e.g. COM3")
    log_parser.add_argument("--baud", type=int, default=115200)
    log_parser.set_defaults(func=_cmd_log)

    analyze_parser = sub.add_parser("analyze", help="compute state-vs-state MVP metrics")
    analyze_parser.add_argument("--input", required=True)
    analyze_parser.add_argument("--max-dt-s", type=float, default=0.02)
    analyze_parser.set_defaults(func=_cmd_analyze)

    sync_parser = sub.add_parser("sync", help="estimate Arduino/iPhone time offset from gyro norms")
    sync_parser.add_argument("--input", required=True)
    sync_parser.add_argument("--reference-source", default=Source.IPHONE.value)
    sync_parser.add_argument("--moving-source", default=Source.ARDUINO.value)
    sync_parser.add_argument("--max-lag-s", type=float, default=2.0)
    sync_parser.add_argument("--step-s", type=float, default=0.005)
    sync_parser.add_argument("--sample-period-s", type=float, default=0.01)
    sync_parser.set_defaults(func=_cmd_sync)

    web_parser = sub.add_parser("web", help="serve browser test UI and write posted messages to JSONL")
    web_parser.add_argument("--host", default="127.0.0.1")
    web_parser.add_argument("--port", type=int, default=8765)
    web_parser.add_argument("--out", default="../logs/web_test.jsonl")
    web_parser.add_argument("--static-dir")
    web_parser.set_defaults(func=_cmd_web)

    receive_file_parser = sub.add_parser("receive-file", help="receive completed Android log uploads over HTTP")
    receive_file_parser.add_argument("--host", default="0.0.0.0")
    receive_file_parser.add_argument("--port", type=int, default=8766)
    receive_file_parser.add_argument("--out-dir", default="../logs/uploads")
    receive_file_parser.set_defaults(func=_cmd_receive_file)

    stats_parser = sub.add_parser("stats", help="summarize log size, rate, and projected storage use")
    stats_parser.add_argument("--input", required=True)
    stats_parser.set_defaults(func=_cmd_stats)

    evaluate_parser = sub.add_parser("evaluate", help="offline state-vs-state evaluation with optional gyro sync")
    evaluate_parser.add_argument("--input", required=True)
    evaluate_parser.add_argument("--reference-source", default=Source.ANDROID.value)
    evaluate_parser.add_argument("--estimator-source", default=Source.ARDUINO.value)
    evaluate_parser.add_argument("--max-dt-s", type=float, default=0.05)
    evaluate_parser.add_argument("--time-offset-s", type=float, default=0.0)
    evaluate_parser.add_argument("--sync-from-gyro", action="store_true")
    evaluate_parser.add_argument("--sync-max-lag-s", type=float, default=2.0)
    evaluate_parser.add_argument("--csv-out")
    evaluate_parser.add_argument("--plots-dir")
    evaluate_parser.add_argument("--summary-out")
    evaluate_parser.set_defaults(func=_cmd_evaluate)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
