"""Simplified gravity-turn steering.

The vehicle holds a vertical attitude for a short time, pitches over toward
the downrange direction by a fixed angle, and then points thrust along the
velocity vector. This is a common textbook sketch, not a closed-loop
guidance algorithm.
"""

from __future__ import annotations

import math


def radial_and_downrange_unit(x: float, y: float) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return (radial_out, downrange) unit vectors in the Earth-centered plane.

    The launch point is (0, R), so downrange starts in the +x direction.
    """
    r = math.hypot(x, y)
    if r == 0:
        return (0.0, 1.0), (1.0, 0.0)
    radial = (x / r, y / r)
    downrange = (y / r, -x / r)
    return radial, downrange


def thrust_direction(
    *,
    x: float,
    y: float,
    vx: float,
    vy: float,
    t: float,
    vertical_hold_s: float,
    pitch_kick_deg: float,
    follow_velocity_after_s: float,
    mode: str,
) -> tuple[float, float]:
    """Return a unit thrust vector in the Earth-centered plane."""
    if mode == "1d":
        return (0.0, 1.0) if y >= 0 else (0.0, -1.0)

    radial, downrange = radial_and_downrange_unit(x, y)
    if t <= vertical_hold_s:
        return radial

    kick = math.radians(pitch_kick_deg)
    kicked = (
        math.cos(kick) * radial[0] + math.sin(kick) * downrange[0],
        math.cos(kick) * radial[1] + math.sin(kick) * downrange[1],
    )
    mag = math.hypot(*kicked)
    if mag == 0:
        kicked = radial
    else:
        kicked = (kicked[0] / mag, kicked[1] / mag)

    if t < follow_velocity_after_s:
        return kicked

    speed = math.hypot(vx, vy)
    if speed < 1.0:
        return kicked
    return (vx / speed, vy / speed)


def pitch_from_vertical_deg(x: float, y: float, tx: float, ty: float) -> float:
    """Angle in degrees between the local vertical and the thrust vector."""
    radial, _ = radial_and_downrange_unit(x, y)
    dot = max(-1.0, min(1.0, radial[0] * tx + radial[1] * ty))
    return math.degrees(math.acos(dot))
