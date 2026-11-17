import json
from pathlib import Path

import pytest

from launch_stack.constants import G0
from launch_stack.vehicle import Stage, Vehicle, load_vehicle


def two_stage() -> Vehicle:
    return Vehicle(
        name="demo",
        stages=[
            Stage("first", dry_mass_kg=1000, propellant_mass_kg=4000, thrust_n=80_000, isp_s=250),
            Stage("second", dry_mass_kg=400, propellant_mass_kg=1600, thrust_n=20_000, isp_s=300),
        ],
        payload_mass_kg=200,
        cd=0.3,
        ref_area_m2=2.0,
    )


def test_wet_mass_includes_every_stage_and_payload():
    v = two_stage()
    assert v.mass_kg() == 200 + 1000 + 4000 + 400 + 1600


def test_mass_flow_matches_thrust_over_exhaust_velocity():
    stage = two_stage().current_stage()
    assert stage is not None
    assert abs(stage.mass_flow_kg_s - (80_000 / (250 * G0))) < 1e-9


def test_staging_drops_spent_stage_dry_mass():
    v = two_stage()
    # Burn the first stage all the way down.
    while v.current_stage_index == 0:
        v.consume(1.0)
    assert v.stage_number == 2
    assert v.mass_kg() == 200 + 400 + 1600


def test_last_stage_dry_mass_stays_attached_after_burnout():
    v = two_stage()
    while v.current_stage_index == 0:
        v.consume(1.0)
    events = {}
    while "burnout" not in events:
        events = v.consume(1.0)
    assert v.stage_number == 2
    assert v.mass_kg() == 200 + 400
    assert v.thrust_n() == 0


def test_rejects_empty_stage_list():
    with pytest.raises(ValueError, match="at least one stage"):
        Vehicle(name="x", stages=[], payload_mass_kg=1, cd=0, ref_area_m2=1)


def test_load_vehicle_round_trip(tmp_path: Path):
    original = two_stage()
    path = tmp_path / "v.json"
    path.write_text(
        json.dumps(
            {
                "name": original.name,
                "payload_mass_kg": original.payload_mass_kg,
                "cd": original.cd,
                "ref_area_m2": original.ref_area_m2,
                "stages": [
                    {
                        "name": s.name,
                        "dry_mass_kg": s.dry_mass_kg,
                        "propellant_mass_kg": s.propellant_mass_kg,
                        "thrust_n": s.thrust_n,
                        "isp_s": s.isp_s,
                    }
                    for s in original.stages
                ],
            }
        )
    )
    loaded = load_vehicle(path)
    assert loaded.mass_kg() == original.mass_kg()
    assert loaded.stages[0].name == "first"


def test_load_vehicle_rejects_missing_fields(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text('{"name": "x", "stages": [{"name": "s"}], "payload_mass_kg": 1, "cd": 0, "ref_area_m2": 1}')
    with pytest.raises(ValueError, match="dry_mass_kg"):
        load_vehicle(path)
