import json
from pathlib import Path

import pytest

from launch_stack.checklist import evaluate_checklist, load_checklist
from launch_stack.simulator import SimulationConfig, simulate
from launch_stack.telemetry import write_telemetry, ingest_telemetry
from launch_stack.vehicle import Stage, Vehicle


CHECKLIST = {
    "schema": "launch-stack-checklist/v0.1",
    "name": "unit checklist",
    "gates": [
        {
            "id": "liftoff",
            "label": "leave the pad",
            "when": {"event": "liftoff"},
            "require": {"thrust_to_weight": {">=": 1.0}},
        },
        {
            "id": "max_q",
            "when": {"event": "max_q"},
            "require": {"dynamic_pressure_pa": {"<=": 200000}},
        },
    ],
}


def strong() -> Vehicle:
    return Vehicle(
        name="strong",
        stages=[
            Stage("first", dry_mass_kg=8000, propellant_mass_kg=42000, thrust_n=1_200_000, isp_s=280),
            Stage("second", dry_mass_kg=2000, propellant_mass_kg=12000, thrust_n=250_000, isp_s=320),
        ],
        payload_mass_kg=500,
        cd=0.3,
        ref_area_m2=3.2,
    )


def test_all_gates_go_on_a_healthy_flight(tmp_path: Path):
    traj = simulate(strong(), SimulationConfig(mode="2d", t_max=600, dt=0.1))
    stream = ingest_telemetry(write_telemetry(traj, tmp_path / "t.jsonl"))
    report = evaluate_checklist(stream, CHECKLIST)
    assert report.decision == "go"
    assert all(g.decision == "go" for g in report.gates)


def test_no_go_when_a_limit_is_too_tight(tmp_path: Path):
    traj = simulate(strong(), SimulationConfig(mode="2d", t_max=600, dt=0.1))
    stream = ingest_telemetry(write_telemetry(traj, tmp_path / "t.jsonl"))
    tight = json.loads(json.dumps(CHECKLIST))
    tight["gates"][1]["require"] = {"dynamic_pressure_pa": {"<=": 1.0}}
    report = evaluate_checklist(stream, tight)
    assert report.decision == "no-go"
    assert report.gates[0].decision == "go"
    assert report.gates[1].decision == "no-go"
    assert "dynamic_pressure_pa" in report.gates[1].reason


def test_no_go_when_the_event_is_missing(tmp_path: Path):
    traj = simulate(strong(), SimulationConfig(mode="1d", t_max=5, dt=0.1, stop_after_apogee=False))
    # 5 seconds is enough for liftoff but not apogee.
    stream = ingest_telemetry(write_telemetry(traj, tmp_path / "t.jsonl"))
    checklist = {
        "schema": "launch-stack-checklist/v0.1",
        "name": "needs apogee",
        "gates": [
            {
                "id": "apogee",
                "when": {"event": "apogee"},
                "require": {"alt_m": {">=": 1000}},
            }
        ],
    }
    # The stream may still have an inferred apogee (highest sample). Use an
    # event that is definitely absent.
    checklist["gates"][0]["when"]["event"] = "does_not_exist"
    report = evaluate_checklist(stream, checklist)
    assert report.decision == "no-go"
    assert "no telemetry sample" in report.gates[0].reason


def test_load_checklist_rejects_bad_schema(tmp_path: Path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"schema": "nope", "name": "x", "gates": []}))
    with pytest.raises(ValueError, match="schema"):
        load_checklist(path)


def test_example_checklist_is_go_for_the_example_vehicle():
    from pathlib import Path as P
    root = P(__file__).resolve().parents[1]
    from launch_stack.vehicle import load_vehicle

    vehicle = load_vehicle(root / "examples" / "two_stage_vehicle.json")
    checklist = load_checklist(root / "examples" / "ascent_checklist.json")
    traj = simulate(vehicle, SimulationConfig(mode="2d", t_max=600, dt=0.1))
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        stream = ingest_telemetry(write_telemetry(traj, P(td) / "t.jsonl"))
    report = evaluate_checklist(stream, checklist)
    assert report.decision == "go", [g.reason for g in report.gates if g.decision != "go"]
