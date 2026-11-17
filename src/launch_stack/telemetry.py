"""JSON Lines telemetry format and ingest.

Schema name: launch-stack-telemetry/v0.1
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .simulator import Sample, Trajectory

SCHEMA = "launch-stack-telemetry/v0.1"
HEADER_TYPE = "header"
SAMPLE_TYPE = "sample"

REQUIRED_SAMPLE_FIELDS = (
    "t",
    "x_m",
    "y_m",
    "vx_mps",
    "vy_mps",
    "alt_m",
    "downrange_m",
    "speed_mps",
    "mass_kg",
    "thrust_n",
    "stage",
    "density_kg_m3",
    "dynamic_pressure_pa",
    "pitch_deg",
    "thrust_to_weight",
    "lifted_off",
)


@dataclass
class TelemetryStream:
    header: dict[str, Any]
    samples: list[dict[str, Any]] = field(default_factory=list)
    path: str | None = None

    def sample_at_event(self, event: str, stage: int | None = None) -> dict[str, Any] | None:
        matches = [
            s
            for s in self.samples
            if s.get("event") == event and (stage is None or s.get("stage") == stage)
        ]
        return matches[0] if matches else None

    def max_q_sample(self) -> dict[str, Any] | None:
        tagged = self.sample_at_event("max_q")
        if tagged:
            return tagged
        flying = [s for s in self.samples if s.get("lifted_off")]
        if not flying:
            return None
        return max(flying, key=lambda s: s["dynamic_pressure_pa"])

    def apogee_sample(self) -> dict[str, Any] | None:
        tagged = self.sample_at_event("apogee")
        if tagged:
            return tagged
        if not self.samples:
            return None
        return max(self.samples, key=lambda s: s["alt_m"])

    def summary(self) -> dict[str, Any]:
        liftoff = self.sample_at_event("liftoff")
        max_q = self.max_q_sample()
        apogee = self.apogee_sample()
        staging = [s for s in self.samples if s.get("event") == "staging"]
        burnout = [s for s in self.samples if s.get("event") == "burnout"]
        return {
            "vehicle": self.header.get("vehicle"),
            "mode": self.header.get("mode"),
            "sample_count": len(self.samples),
            "liftoff_s": None if liftoff is None else liftoff["t"],
            "max_q_pa": None if max_q is None else max_q["dynamic_pressure_pa"],
            "max_q_s": None if max_q is None else max_q["t"],
            "apogee_m": None if apogee is None else apogee["alt_m"],
            "apogee_s": None if apogee is None else apogee["t"],
            "staging_events": len(staging),
            "burnout_events": len(burnout),
            "final_speed_mps": None if not self.samples else self.samples[-1]["speed_mps"],
            "final_alt_m": None if not self.samples else self.samples[-1]["alt_m"],
        }


def sample_to_record(sample: Sample) -> dict[str, Any]:
    record: dict[str, Any] = {
        "type": SAMPLE_TYPE,
        "t": sample.t,
        "x_m": sample.x_m,
        "y_m": sample.y_m,
        "vx_mps": sample.vx_mps,
        "vy_mps": sample.vy_mps,
        "alt_m": sample.alt_m,
        "downrange_m": sample.downrange_m,
        "speed_mps": sample.speed_mps,
        "mass_kg": sample.mass_kg,
        "thrust_n": sample.thrust_n,
        "stage": sample.stage,
        "density_kg_m3": sample.density_kg_m3,
        "dynamic_pressure_pa": sample.dynamic_pressure_pa,
        "pitch_deg": sample.pitch_deg,
        "thrust_to_weight": sample.thrust_to_weight,
        "lifted_off": sample.lifted_off,
        "event": sample.event,
    }
    return record


def header_from_trajectory(traj: Trajectory) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "type": HEADER_TYPE,
        "vehicle": traj.vehicle_name,
        "mode": traj.mode,
        "dt": traj.config.dt,
        "notes": traj.notes,
        "simplifications": [
            "spherical non-rotating Earth",
            "exponential atmosphere",
            "constant vacuum thrust and specific impulse",
            "instant staging mass drop",
            "simple gravity-turn steering",
        ],
    }


def tag_max_q(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copy samples and mark the peak dynamic-pressure sample as max_q.

    Existing event tags (liftoff, staging, and so on) are left in place.
    If the peak already has an event, a separate max_q field is set and
    the event name is kept. If it has no event, event becomes max_q.
    """
    out = [dict(r) for r in records]
    flying = [r for r in out if r.get("lifted_off") and r.get("type") == SAMPLE_TYPE]
    if not flying:
        return out
    peak = max(flying, key=lambda s: s.get("dynamic_pressure_pa", 0.0))
    if peak.get("event"):
        peak["max_q"] = True
    else:
        peak["event"] = "max_q"
        peak["max_q"] = True
    return out


def write_telemetry(traj: Trajectory, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = header_from_trajectory(traj)
    samples = tag_max_q(sample_to_record(s) for s in traj.samples)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(header) + "\n")
        for record in samples:
            handle.write(json.dumps(record) + "\n")
    return path


def _validate_header(obj: Any, line_no: int) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise ValueError(f"line {line_no}: header must be a JSON object")
    if obj.get("schema") != SCHEMA:
        raise ValueError(
            f"line {line_no}: expected schema {SCHEMA!r}, got {obj.get('schema')!r}"
        )
    if obj.get("type") != HEADER_TYPE:
        raise ValueError(f"line {line_no}: first record must have type {HEADER_TYPE!r}")
    return obj


def _validate_sample(obj: Any, line_no: int) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise ValueError(f"line {line_no}: sample must be a JSON object")
    if obj.get("type") != SAMPLE_TYPE:
        raise ValueError(f"line {line_no}: expected type {SAMPLE_TYPE!r}")
    missing = [f for f in REQUIRED_SAMPLE_FIELDS if f not in obj]
    if missing:
        raise ValueError(f"line {line_no}: sample missing fields {missing}")
    return obj


def ingest_telemetry(path: str | Path) -> TelemetryStream:
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    records: list[Any] = []
    for i, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            records.append((i, json.loads(line)))
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {i}: invalid JSON ({exc.msg})") from exc
    if not records:
        raise ValueError("telemetry file is empty")
    header = _validate_header(records[0][1], records[0][0])
    samples = [_validate_sample(obj, line_no) for line_no, obj in records[1:]]
    return TelemetryStream(header=header, samples=samples, path=str(path))
