"""Simplified exponential atmosphere.

This is an educational stand-in, not the International Standard Atmosphere
and not a winds or temperature model.
"""

from __future__ import annotations

import math

from .constants import EARTH_RADIUS_M, RHO0_KG_M3, SCALE_HEIGHT_M


def geodetic_altitude_m(radius_m: float, earth_radius_m: float = EARTH_RADIUS_M) -> float:
    """Height above the spherical Earth surface, in meters."""
    return radius_m - earth_radius_m


def density_kg_m3(altitude_m: float) -> float:
    """Return air density at a geometric altitude.

    Below the surface the density is defined as sea-level density, only so
    the integrator has a finite value; the simulator treats a negative
    altitude after liftoff as impact and stops.
    """
    if altitude_m <= 0:
        return RHO0_KG_M3
    return RHO0_KG_M3 * math.exp(-altitude_m / SCALE_HEIGHT_M)


def dynamic_pressure_pa(density: float, speed_mps: float) -> float:
    """q = 1/2 rho v^2, in pascals."""
    return 0.5 * density * speed_mps * speed_mps
