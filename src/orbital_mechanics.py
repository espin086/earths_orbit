"""Orbital mechanics for the Earth's Orbit classroom visualization.

Physics: Keplerian two-body orbits. Positions come from solving Kepler's
equation (M = E - e*sin(E)) for the eccentric anomaly, then converting to
true anomaly and Cartesian coordinates in the orbital plane.

Units: AU for distance, days for time (matches what a 5th grader already
knows — "days" and "years" — instead of SI meters/seconds).
"""

from dataclasses import dataclass

import numpy as np

# Astronomical unit in km, for the scale/exponents panel.
AU_KM = 149_597_870.7


@dataclass(frozen=True)
class Planet:
    name: str
    semi_major_axis_au: float  # a
    eccentricity: float  # e
    period_days: float  # T (sidereal orbital period)
    color: str
    radius_km: float  # for a size-comparison panel, not orbit scale

    @property
    def semi_major_axis_km(self) -> float:
        return self.semi_major_axis_au * AU_KM


# Real values (JPL/NASA planetary fact sheet), enough for the Kepler's
# Third Law demo (T^2 proportional to a^3) to actually land visually.
PLANETS: list[Planet] = [
    Planet("Mercury", 0.387, 0.206, 87.97, "#b1adad", 2439.7),
    Planet("Venus", 0.723, 0.007, 224.70, "#e6c27a", 6051.8),
    Planet("Earth", 1.000, 0.0167, 365.25, "#3f8efc", 6371.0),
    Planet("Mars", 1.524, 0.093, 686.98, "#c1440e", 3389.5),
    Planet("Jupiter", 5.203, 0.049, 4332.59, "#d8ae7e", 69911.0),
    Planet("Saturn", 9.537, 0.0565, 10759.22, "#e3c16f", 58232.0),
    Planet("Uranus", 19.191, 0.0457, 30688.5, "#9fd9d9", 25362.0),
]

EARTH = PLANETS[2]

# Axial tilt used for the day/night + seasons panel.
EARTH_AXIAL_TILT_DEG = 23.44


def solve_eccentric_anomaly(mean_anomaly: np.ndarray, eccentricity: float, tol: float = 1e-8) -> np.ndarray:
    """Solve Kepler's equation M = E - e*sin(E) for E, via Newton's method."""
    E = mean_anomaly.copy()
    for _ in range(50):
        delta = (E - eccentricity * np.sin(E) - mean_anomaly) / (1 - eccentricity * np.cos(E))
        E -= delta
        if np.max(np.abs(delta)) < tol:
            break
    return E


def orbit_positions(planet: Planet, n_points: int = 720) -> tuple[np.ndarray, np.ndarray]:
    """Full ellipse trace (x, y) in AU, Sun at one focus (origin)."""
    mean_anomaly = np.linspace(0, 2 * np.pi, n_points)
    E = solve_eccentric_anomaly(mean_anomaly, planet.eccentricity)
    a, e = planet.semi_major_axis_au, planet.eccentricity
    x = a * (np.cos(E) - e)
    y = a * np.sqrt(1 - e**2) * np.sin(E)
    return x, y


def position_at_time(planet: Planet, day: float) -> tuple[float, float]:
    """Planet's (x, y) position in AU at a given day since perihelion."""
    mean_anomaly = 2 * np.pi * (day % planet.period_days) / planet.period_days
    E = solve_eccentric_anomaly(np.array([mean_anomaly]), planet.eccentricity)[0]
    a, e = planet.semi_major_axis_au, planet.eccentricity
    x = a * (np.cos(E) - e)
    y = a * np.sqrt(1 - e**2) * np.sin(E)
    return float(x), float(y)


def ellipse_area_au2(planet: Planet) -> float:
    """Area of the orbital ellipse: A = pi * a * b, with b = a * sqrt(1 - e^2).

    This is the direct 5th-grade geometry hook — "area of an ellipse" as a
    natural extension of "area of a circle" (A = pi * r^2), since a circle
    is just an ellipse with a == b.
    """
    a = planet.semi_major_axis_au
    b = a * np.sqrt(1 - planet.eccentricity**2)
    return float(np.pi * a * b)


def kepler_third_law_check(planet: Planet) -> tuple[float, float]:
    """Return (a^3, T_years^2) — should be equal for every planet.

    This is the exponents hook: T^2 is proportional to a^3. Plotting a^3
    against T^2 for every planet in the solar system produces one straight
    line, which is a very concrete "why do we use exponents" demo.
    """
    a_cubed = planet.semi_major_axis_au**3
    t_years = planet.period_days / 365.25
    t_squared = t_years**2
    return a_cubed, t_squared
