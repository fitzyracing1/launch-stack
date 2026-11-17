"""Physical constants and clearly labeled simplifications.

These values are standard approximations, good enough for an educational
ascent sketch. They are not a high-fidelity Earth or atmosphere model.
"""

# Newtonian gravitational constant (CODATA 2018), m^3 kg^-1 s^-2.
G = 6.67430e-11

# Approximate Earth mass, kg. A spherical, non-rotating Earth is assumed.
EARTH_MASS_KG = 5.972e24

# Approximate volumetric mean Earth radius, m.
EARTH_RADIUS_M = 6.371e6

# Standard gravity, m/s^2. Used only to convert specific impulse to exhaust
# velocity (v_ex = Isp * G0). This is not the local gravity in the simulator.
G0 = 9.80665

# Sea-level air density for a simple exponential atmosphere, kg/m^3.
RHO0_KG_M3 = 1.225

# Scale height for the educational exponential atmosphere, m.
# Density is modeled as rho0 * exp(-altitude / SCALE_HEIGHT_M).
# Real atmospheres vary with temperature, composition, and latitude.
SCALE_HEIGHT_M = 8500.0
