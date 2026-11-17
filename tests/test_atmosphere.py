import math

from launch_stack.atmosphere import density_kg_m3, dynamic_pressure_pa, geodetic_altitude_m
from launch_stack.constants import EARTH_RADIUS_M, RHO0_KG_M3, SCALE_HEIGHT_M


def test_altitude_at_surface_is_zero():
    assert geodetic_altitude_m(EARTH_RADIUS_M) == 0


def test_altitude_above_surface():
    assert geodetic_altitude_m(EARTH_RADIUS_M + 1000) == 1000


def test_sea_level_density():
    assert density_kg_m3(0) == RHO0_KG_M3


def test_density_falls_by_e_at_scale_height():
    got = density_kg_m3(SCALE_HEIGHT_M)
    assert math.isclose(got, RHO0_KG_M3 / math.e, rel_tol=1e-9)


def test_density_is_tiny_in_near_space():
    # Educational model only: at 120 km the exponential has already dropped
    # by many orders of magnitude.
    assert density_kg_m3(120_000) < 1e-4


def test_dynamic_pressure_scales_with_speed_squared():
    rho = 1.0
    assert dynamic_pressure_pa(rho, 10) * 4 == dynamic_pressure_pa(rho, 20)
