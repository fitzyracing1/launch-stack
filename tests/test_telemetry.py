import json
from pathlib import Path

import pytest

from launch_stack.simulator import SimulationConfig, simulate
from launch_stack.telemetry import SCHEMA, ingest_telemetry, write_telemetry
from launch_stack.vehicle import Stage, Vehicle


def vehicle() -> Vehicle:
    return Vehicle(
        name="tele-demo",
        stages=[
            Stage("first", dry_mass_kg=8000, propellant_mass_kg=42000, thrust_n=1_200_000, isp_s=280),
            Stage("second", dry_mass_kg=2000, propellant_mass_kg=12000, thrust_n=250_000, isp_s=320),
        ],
        payload_mass_kg=500,
        cd=0.3,
        ref_area_m2=3.2,
    )


def test_round_trip_preserves_samples_and_header(tmp_path: Path):
    traj = simulate(vehicle(), SimulationConfig(mode="2d", t_max=80, dt=0.2, record_every_s=1.0))
    path = write_telemetry(traj, tmp_path / "ascent.jsonl")
    stream = ingest_telemetry(path)
    assert stream.header["schema"] == SCHEMA
    assert stream.header["vehicle"] == "tele-demo"
    assert stream.header["mode"] == "2d"
    assert "educational" in stream.header["notes"].lower() or "simplified" in stream.header["notes"].lower()
    assert len(stream.samples) == len(traj.samples)
    assert stream.samples[0]["t"] == traj.samples[0].t


def test_ingest_summary_has_liftoff_and_max_q(tmp_path: Path):
    traj = simulate(vehicle(), SimulationConfig(mode="2d", t_max=200, dt=0.1))
    path = write_telemetry(traj, tmp_path / "ascent.jsonl")
    summary = ingest_telemetry(path).summary()
    assert summary["liftoff_s"] is not None
    assert summary["max_q_pa"] > 0
    assert summary["staging_events"] >= 1
    assert summary["sample_count"] == len(traj.samples)


def test_rejects_empty_file(tmp_path: Path):
    path = tmp_path / "empty.jsonl"
    path.write_text("")
    with pytest.raises(ValueError, match="empty"):
        ingest_telemetry(path)


def test_rejects_wrong_schema(tmp_path: Path):
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps({"schema": "nope", "type": "header"}) + "\n")
    with pytest.raises(ValueError, match="schema"):
        ingest_telemetry(path)


def test_rejects_sample_missing_fields(tmp_path: Path):
    path = tmp_path / "bad.jsonl"
    header = {"schema": SCHEMA, "type": "header", "vehicle": "x", "mode": "1d"}
    path.write_text(json.dumps(header) + "\n" + json.dumps({"type": "sample", "t": 0}) + "\n")
    with pytest.raises(ValueError, match="missing fields"):
        ingest_telemetry(path)


def test_rejects_invalid_json(tmp_path: Path):
    path = tmp_path / "bad.jsonl"
    path.write_text("{" + "\n")
    with pytest.raises(ValueError, match="invalid JSON"):
        ingest_telemetry(path)
