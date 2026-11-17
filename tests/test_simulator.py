import math

from launch_stack.constants import EARTH_RADIUS_M, G, EARTH_MASS_KG, G0
from launch_stack.simulator import SimulationConfig, simulate, surface_gravity
from launch_stack.vehicle import Stage, Vehicle


def weak_vehicle() -> Vehicle:
    return Vehicle(
        name="too-weak",
        stages=[Stage("only", dry_mass_kg=1000, propellant_mass_kg=1000, thrust_n=1_000, isp_s=250)],
        payload_mass_kg=100,
        cd=0.3,
        ref_area_m2=1.0,
    )


def strong_single() -> Vehicle:
    return Vehicle(
        name="strong-single",
        stages=[
            Stage("only", dry_mass_kg=2000, propellant_mass_kg=8000, thrust_n=200_000, isp_s=300)
        ],
        payload_mass_kg=200,
        cd=0.3,
        ref_area_m2=2.0,
    )


def two_stage() -> Vehicle:
    return Vehicle(
        name="two-stage",
        stages=[
            Stage("first", dry_mass_kg=8000, propellant_mass_kg=42000, thrust_n=1_200_000, isp_s=280),
            Stage("second", dry_mass_kg=2000, propellant_mass_kg=12000, thrust_n=250_000, isp_s=320),
        ],
        payload_mass_kg=500,
        cd=0.3,
        ref_area_m2=3.2,
    )


def test_surface_gravity_is_about_9_8():
    g = surface_gravity(SimulationConfig())
    assert 9.7 < g < 9.9


def test_weak_vehicle_stays_on_the_pad():
    traj = simulate(
        weak_vehicle(),
        SimulationConfig(mode="1d", t_max=20, dt=0.1, stop_after_apogee=False),
    )
    assert not any(s.event == "liftoff" for s in traj.samples)
    assert all(s.alt_m == 0 and not s.lifted_off for s in traj.samples)


def test_strong_vehicle_lifts_off_in_1d():
    traj = simulate(
        strong_single(),
        SimulationConfig(mode="1d", t_max=40, dt=0.1, record_every_s=0.5),
    )
    assert any(s.event == "liftoff" for s in traj.samples)
    assert max(s.alt_m for s in traj.samples) > 1000


def test_vacuum_1d_burn_matches_rocket_equation():
    vehicle = Vehicle(
        name="vacuum-burn",
        stages=[Stage("only", dry_mass_kg=1000, propellant_mass_kg=3000, thrust_n=50_000, isp_s=300)],
        payload_mass_kg=200,
        cd=0.0,
        ref_area_m2=1.0,
    )
    traj = simulate(
        vehicle,
        SimulationConfig(
            mode="1d",
            dt=0.05,
            t_max=200,
            enable_gravity=False,
            enable_atmosphere=False,
            record_every_s=0.5,
        ),
    )
    burnout = next(s for s in traj.samples if s.event == "burnout")
    m0 = 200 + 1000 + 3000
    mf = 200 + 1000
    expected = 300 * G0 * math.log(m0 / mf)
    assert abs(burnout.speed_mps - expected) / expected < 0.02


def test_drag_slows_the_vehicle_down():
    vehicle = strong_single()
    vacuum = simulate(
        vehicle,
        SimulationConfig(mode="1d", t_max=40, dt=0.1, enable_atmosphere=False, stop_after_apogee=False),
    )
    air = simulate(
        vehicle,
        SimulationConfig(mode="1d", t_max=40, dt=0.1, enable_atmosphere=True, stop_after_apogee=False),
    )
    # Compare speed at the same time while both are still burning.
    t = 15.0
    v_vac = min(vacuum.samples, key=lambda s: abs(s.t - t)).speed_mps
    v_air = min(air.samples, key=lambda s: abs(s.t - t)).speed_mps
    assert v_air < v_vac


def test_gravity_turn_sends_the_vehicle_downrange():
    traj = simulate(
        two_stage(),
        SimulationConfig(mode="2d", t_max=80, dt=0.1, vertical_hold_s=8, pitch_kick_deg=7, follow_velocity_after_s=12),
    )
    late = [s for s in traj.samples if s.t >= 20 and s.lifted_off]
    assert late
    assert late[-1].downrange_m > 1000
    assert late[-1].pitch_deg > 5


def test_two_stage_flight_records_staging_and_reaches_space():
    traj = simulate(
        two_stage(),
        SimulationConfig(mode="2d", t_max=600, dt=0.1),
    )
    events = [s.event for s in traj.samples if s.event]
    assert "liftoff" in events
    assert "staging" in events
    assert "burnout" in events
    assert max(s.alt_m for s in traj.samples) > 100_000


def test_staging_drops_mass_discontinuously():
    traj = simulate(
        two_stage(),
        SimulationConfig(mode="2d", t_max=200, dt=0.1, record_every_s=0.1),
    )
    staging = next(s for s in traj.samples if s.event == "staging")
    # The sample just before staging should still include first-stage dry mass.
    prior = [s for s in traj.samples if s.t < staging.t and s.stage == 1]
    assert prior
    assert staging.mass_kg < prior[-1].mass_kg - 1000
    assert staging.stage == 2


def test_1d_motion_has_no_downrange():
    traj = simulate(
        strong_single(),
        SimulationConfig(mode="1d", t_max=30, dt=0.1),
    )
    assert all(s.x_m == 0 and s.downrange_m == 0 for s in traj.samples)


def test_rejects_bad_dt():
    import pytest

    with pytest.raises(ValueError, match="dt"):
        simulate(strong_single(), SimulationConfig(dt=0))
