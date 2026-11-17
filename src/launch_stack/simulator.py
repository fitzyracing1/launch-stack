"""1D and 2D launch-and-ascent integrator.

The integration is a fixed-step velocity Verlet / RK4 hybrid: RK4 for the
translational state with mass and thrust held constant across the substeps,
then a propellant update and optional staging at the end of the step. That
is accurate enough for this educational model and keeps the tests stable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Literal

from .atmosphere import density_kg_m3, dynamic_pressure_pa, geodetic_altitude_m
from .constants import EARTH_MASS_KG, EARTH_RADIUS_M, G
from .guidance import pitch_from_vertical_deg, thrust_direction
from .vehicle import Vehicle


Mode = Literal["1d", "2d"]


@dataclass
class SimulationConfig:
    mode: Mode = "2d"
    dt: float = 0.1
    t_max: float = 600.0
    vertical_hold_s: float = 8.0
    pitch_kick_deg: float = 7.0
    follow_velocity_after_s: float = 12.0
    record_every_s: float = 0.5
    enable_gravity: bool = True
    enable_atmosphere: bool = True
    earth_radius_m: float = EARTH_RADIUS_M
    earth_mass_kg: float = EARTH_MASS_KG
    # Stop a short while after apogee once the last stage has burned out,
    # so coasting samples are available without running to t_max.
    stop_after_apogee: bool = True


@dataclass
class Sample:
    t: float
    x_m: float
    y_m: float
    vx_mps: float
    vy_mps: float
    alt_m: float
    downrange_m: float
    speed_mps: float
    mass_kg: float
    thrust_n: float
    stage: int
    density_kg_m3: float
    dynamic_pressure_pa: float
    pitch_deg: float
    thrust_to_weight: float
    lifted_off: bool
    event: str | None = None


@dataclass
class Trajectory:
    vehicle_name: str
    mode: str
    config: SimulationConfig
    samples: list[Sample] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    impact: bool = False
    notes: str = (
        "Educational simplified ascent. Spherical non-rotating Earth, "
        "exponential atmosphere, constant vacuum thrust and Isp, simple gravity turn."
    )


def surface_gravity(config: SimulationConfig) -> float:
    return G * config.earth_mass_kg / (config.earth_radius_m ** 2)


def _acceleration(
    x: float,
    y: float,
    vx: float,
    vy: float,
    mass: float,
    thrust_n: float,
    thrust_dir: tuple[float, float],
    vehicle: Vehicle,
    config: SimulationConfig,
) -> tuple[float, float]:
    ax = 0.0
    ay = 0.0
    r = math.hypot(x, y)
    if config.enable_gravity and r > 0:
        accel_g = G * config.earth_mass_kg / (r * r)
        ax -= accel_g * x / r
        ay -= accel_g * y / r
    if thrust_n > 0 and mass > 0:
        ax += (thrust_n / mass) * thrust_dir[0]
        ay += (thrust_n / mass) * thrust_dir[1]
    if config.enable_atmosphere and mass > 0:
        alt = geodetic_altitude_m(r, config.earth_radius_m)
        rho = density_kg_m3(alt)
        speed = math.hypot(vx, vy)
        if speed > 0:
            drag = 0.5 * vehicle.cd * rho * speed * speed * vehicle.ref_area_m2
            ax -= (drag / mass) * vx / speed
            ay -= (drag / mass) * vy / speed
    return ax, ay


def _make_sample(
    t: float,
    x: float,
    y: float,
    vx: float,
    vy: float,
    vehicle: Vehicle,
    thrust_dir: tuple[float, float],
    config: SimulationConfig,
    lifted_off: bool,
    event: str | None,
) -> Sample:
    r = math.hypot(x, y)
    alt = geodetic_altitude_m(r, config.earth_radius_m)
    # Downrange along the spherical surface from the launch site at (0, R).
    launch_angle = math.atan2(0.0, config.earth_radius_m)  # 0 at +y axis? atan2(x,y)
    angle = math.atan2(x, y)
    downrange = angle * config.earth_radius_m
    speed = math.hypot(vx, vy)
    rho = density_kg_m3(alt) if config.enable_atmosphere else 0.0
    mass = vehicle.mass_kg()
    thrust = vehicle.thrust_n()
    weight = mass * surface_gravity(config) if mass > 0 else 0.0
    twr = thrust / weight if weight > 0 else 0.0
    return Sample(
        t=t,
        x_m=x,
        y_m=y,
        vx_mps=vx,
        vy_mps=vy,
        alt_m=alt,
        downrange_m=downrange,
        speed_mps=speed,
        mass_kg=mass,
        thrust_n=thrust,
        stage=vehicle.stage_number,
        density_kg_m3=rho,
        dynamic_pressure_pa=dynamic_pressure_pa(rho, speed),
        pitch_deg=pitch_from_vertical_deg(x, y, thrust_dir[0], thrust_dir[1]),
        thrust_to_weight=twr,
        lifted_off=lifted_off,
        event=event,
    )


def simulate(vehicle: Vehicle, config: SimulationConfig | None = None) -> Trajectory:
    if config is None:
        config = SimulationConfig()
    if config.dt <= 0:
        raise ValueError("dt must be positive")
    if config.mode not in ("1d", "2d"):
        raise ValueError("mode must be '1d' or '2d'")

    vehicle = vehicle.copy()
    traj = Trajectory(vehicle_name=vehicle.name, mode=config.mode, config=config)

    x = 0.0
    y = config.earth_radius_m
    vx = 0.0
    vy = 0.0
    t = 0.0
    lifted_off = False
    last_record = -1e9
    peak_alt = 0.0
    saw_burnout = False
    apogee_recorded = False

    def dir_at(tt: float, xx: float, yy: float, vxx: float, vyy: float) -> tuple[float, float]:
        return thrust_direction(
            x=xx,
            y=yy,
            vx=vxx,
            vy=vyy,
            t=tt,
            vertical_hold_s=config.vertical_hold_s,
            pitch_kick_deg=config.pitch_kick_deg,
            follow_velocity_after_s=config.follow_velocity_after_s,
            mode=config.mode,
        )

    def record(event: str | None = None) -> None:
        nonlocal last_record
        sample = _make_sample(
            t, x, y, vx, vy, vehicle, dir_at(t, x, y, vx, vy), config, lifted_off, event
        )
        traj.samples.append(sample)
        last_record = t
        if event:
            traj.events.append({"t": t, "event": event, "stage": sample.stage})

    record("ignition")

    max_steps = int(config.t_max / config.dt) + 2
    for _ in range(max_steps):
        if t >= config.t_max - 1e-12:
            record("time_limit")
            break

        mass = vehicle.mass_kg()
        thrust = vehicle.thrust_n()
        weight = mass * surface_gravity(config)
        if not lifted_off:
            if thrust > weight and mass > 0:
                lifted_off = True
                record("liftoff")
            else:
                # Held on the pad. Still consume no time incorrectly — clocks run.
                # Propellant is burned only after liftoff, so a too-weak vehicle
                # stays on the pad with a full tank.
                t += config.dt
                if t - last_record >= config.record_every_s - 1e-12:
                    record()
                if t >= config.t_max:
                    record("time_limit")
                    break
                continue

        direction = dir_at(t, x, y, vx, vy)
        if config.mode == "1d":
            # In 1D only the radial (vertical at the launch site) axis is kept.
            x = 0.0
            vx = 0.0
            direction = (0.0, 1.0)

        def accel(xx, yy, vxx, vyy):
            return _acceleration(xx, yy, vxx, vyy, mass, thrust, direction, vehicle, config)

        # Classical RK4 for position and velocity.
        ax1, ay1 = accel(x, y, vx, vy)
        k1vx, k1vy = ax1 * config.dt, ay1 * config.dt
        k1x, k1y = vx * config.dt, vy * config.dt

        ax2, ay2 = accel(x + 0.5 * k1x, y + 0.5 * k1y, vx + 0.5 * k1vx, vy + 0.5 * k1vy)
        k2vx, k2vy = ax2 * config.dt, ay2 * config.dt
        k2x, k2y = (vx + 0.5 * k1vx) * config.dt, (vy + 0.5 * k1vy) * config.dt

        ax3, ay3 = accel(x + 0.5 * k2x, y + 0.5 * k2y, vx + 0.5 * k2vx, vy + 0.5 * k2vy)
        k3vx, k3vy = ax3 * config.dt, ay3 * config.dt
        k3x, k3y = (vx + 0.5 * k2vx) * config.dt, (vy + 0.5 * k2vy) * config.dt

        ax4, ay4 = accel(x + k3x, y + k3y, vx + k3vx, vy + k3vy)
        k4vx, k4vy = ax4 * config.dt, ay4 * config.dt
        k4x, k4y = (vx + k3vx) * config.dt, (vy + k3vy) * config.dt

        x += (k1x + 2 * k2x + 2 * k3x + k4x) / 6.0
        y += (k1y + 2 * k2y + 2 * k3y + k4y) / 6.0
        vx += (k1vx + 2 * k2vx + 2 * k3vx + k4vx) / 6.0
        vy += (k1vy + 2 * k2vy + 2 * k3vy + k4vy) / 6.0
        if config.mode == "1d":
            x = 0.0
            vx = 0.0

        events = vehicle.consume(config.dt)
        t += config.dt

        event_name = None
        if events.get("staging"):
            event_name = "staging"
            record(event_name)
        elif events.get("burnout") or (
            thrust > 0 and vehicle.thrust_n() == 0 and vehicle.current_stage() is not None
            and vehicle.remaining_propellant_kg[vehicle.current_stage_index] <= 0
            and vehicle.current_stage_index == len(vehicle.stages) - 1
        ):
            event_name = "burnout"
            saw_burnout = True
            record(event_name)

        r = math.hypot(x, y) if config.mode == "2d" else y
        alt = geodetic_altitude_m(r, config.earth_radius_m)
        if alt < -1.0 and lifted_off:
            traj.impact = True
            record("impact")
            break

        if alt > peak_alt:
            peak_alt = alt

        if (
            config.stop_after_apogee
            and saw_burnout
            and not apogee_recorded
            and alt < peak_alt - 1.0
            and (config.mode == "1d" or vy * y + vx * x < 0)
        ):
            apogee_recorded = True
            record("apogee")
            # Capture a few more samples after apogee, then stop.
            # The current step already recorded apogee.
            # Continue for one more record interval then break at loop end via flag.
        if apogee_recorded and t - last_record >= config.record_every_s and event_name is None:
            record()
            break

        if event_name is None and t - last_record >= config.record_every_s - 1e-12:
            record()

    if not traj.samples or traj.samples[-1].t < t - 1e-12:
        if not traj.impact and (not traj.samples or traj.samples[-1].event not in {"impact", "time_limit", "apogee"}):
            record()

    return traj
