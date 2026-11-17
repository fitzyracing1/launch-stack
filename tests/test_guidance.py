import math

from launch_stack.constants import EARTH_RADIUS_M
from launch_stack.guidance import pitch_from_vertical_deg, radial_and_downrange_unit, thrust_direction


def test_downrange_at_the_launch_site_is_plus_x():
    radial, downrange = radial_and_downrange_unit(0.0, EARTH_RADIUS_M)
    assert radial == (0.0, 1.0)
    assert downrange == (1.0, 0.0)


def test_holds_vertical_before_the_pitch_kick():
    direction = thrust_direction(
        x=0.0,
        y=EARTH_RADIUS_M,
        vx=0.0,
        vy=10.0,
        t=3.0,
        vertical_hold_s=8.0,
        pitch_kick_deg=10.0,
        follow_velocity_after_s=12.0,
        mode="2d",
    )
    assert direction == (0.0, 1.0)


def test_pitch_kick_tilts_toward_downrange():
    direction = thrust_direction(
        x=0.0,
        y=EARTH_RADIUS_M,
        vx=0.0,
        vy=10.0,
        t=9.0,
        vertical_hold_s=8.0,
        pitch_kick_deg=10.0,
        follow_velocity_after_s=12.0,
        mode="2d",
    )
    assert direction[0] > 0
    assert direction[1] > 0
    angle = pitch_from_vertical_deg(0.0, EARTH_RADIUS_M, *direction)
    assert math.isclose(angle, 10.0, abs_tol=1e-6)


def test_later_steering_follows_the_velocity_vector():
    direction = thrust_direction(
        x=1000.0,
        y=EARTH_RADIUS_M + 2000.0,
        vx=300.0,
        vy=400.0,
        t=20.0,
        vertical_hold_s=8.0,
        pitch_kick_deg=10.0,
        follow_velocity_after_s=12.0,
        mode="2d",
    )
    assert math.isclose(direction[0], 0.6, abs_tol=1e-9)
    assert math.isclose(direction[1], 0.8, abs_tol=1e-9)


def test_1d_guidance_stays_vertical():
    direction = thrust_direction(
        x=0.0,
        y=EARTH_RADIUS_M,
        vx=0.0,
        vy=10.0,
        t=30.0,
        vertical_hold_s=8.0,
        pitch_kick_deg=10.0,
        follow_velocity_after_s=12.0,
        mode="1d",
    )
    assert direction == (0.0, 1.0)
