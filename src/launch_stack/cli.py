"""Command-line interface for simulate, ingest, and checklist."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .checklist import evaluate_checklist, load_checklist
from .simulator import SimulationConfig, simulate
from .telemetry import ingest_telemetry, write_telemetry
from .vehicle import load_vehicle


USAGE = """launch-stack — educational rocket mission software starter

Commands:
  launch-stack simulate --vehicle FILE --out FILE [--mode 1d|2d]
  launch-stack ingest FILE
  launch-stack checklist --telemetry FILE --checklist FILE [--out FILE]
"""


def _add_simulate(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("simulate", help="run a 1D or 2D ascent and write telemetry")
    p.add_argument("--vehicle", required=True, help="path to a vehicle JSON file")
    p.add_argument("--out", required=True, help="path for the JSON Lines telemetry file")
    p.add_argument("--mode", choices=("1d", "2d"), default="2d")
    p.add_argument("--dt", type=float, default=0.1, help="integrator step, seconds")
    p.add_argument("--t-max", type=float, default=600.0, help="time limit, seconds")
    p.add_argument("--vertical-hold", type=float, default=8.0, dest="vertical_hold_s")
    p.add_argument("--pitch-kick", type=float, default=7.0, dest="pitch_kick_deg")
    p.add_argument(
        "--follow-velocity-after",
        type=float,
        default=12.0,
        dest="follow_velocity_after_s",
    )
    p.add_argument("--record-every", type=float, default=0.5, dest="record_every_s")
    p.add_argument("--no-atmosphere", action="store_true")
    p.add_argument("--no-gravity", action="store_true")


def _add_ingest(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("ingest", help="read a telemetry stream and print a summary")
    p.add_argument("path", help="path to a JSON Lines telemetry file")


def _add_checklist(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("checklist", help="evaluate a go/no-go checklist against telemetry")
    p.add_argument("--telemetry", required=True)
    p.add_argument("--checklist", required=True)
    p.add_argument("--out", help="optional path to write the report JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="launch-stack",
        description="Educational launch-and-ascent simulator, telemetry ingest, and go/no-go checklist runner.",
    )
    sub = parser.add_subparsers(dest="command")
    _add_simulate(sub)
    _add_ingest(sub)
    _add_checklist(sub)
    return parser


def _cmd_simulate(args: argparse.Namespace) -> int:
    vehicle = load_vehicle(args.vehicle)
    config = SimulationConfig(
        mode=args.mode,
        dt=args.dt,
        t_max=args.t_max,
        vertical_hold_s=args.vertical_hold_s,
        pitch_kick_deg=args.pitch_kick_deg,
        follow_velocity_after_s=args.follow_velocity_after_s,
        record_every_s=args.record_every_s,
        enable_atmosphere=not args.no_atmosphere,
        enable_gravity=not args.no_gravity,
    )
    traj = simulate(vehicle, config)
    path = write_telemetry(traj, args.out)
    from .telemetry import ingest_telemetry as ingest

    summary = ingest(path).summary()
    print(json.dumps({"wrote": str(path), "summary": summary}, indent=2))
    return 0


def _cmd_ingest(args: argparse.Namespace) -> int:
    stream = ingest_telemetry(args.path)
    print(json.dumps(stream.summary(), indent=2))
    return 0


def _cmd_checklist(args: argparse.Namespace) -> int:
    stream = ingest_telemetry(args.telemetry)
    checklist = load_checklist(args.checklist)
    report = evaluate_checklist(stream, checklist)
    payload = report.as_dict()
    text = json.dumps(payload, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report.decision == "go" else 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if not args.command:
        print(USAGE)
        return 1
    try:
        if args.command == "simulate":
            return _cmd_simulate(args)
        if args.command == "ingest":
            return _cmd_ingest(args)
        if args.command == "checklist":
            return _cmd_checklist(args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"launch-stack: {exc}", file=sys.stderr)
        return 1
    parser.error(f"unknown command {args.command}")
    return 1
