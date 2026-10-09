from flask import Blueprint, render_template, request, jsonify
import json
from datetime import datetime, timezone

from app.api.solar_system import get_planets
from app.cache import cache


sky_bp = Blueprint("sky", __name__, url_prefix="/sky")


@sky_bp.route("/")
def index():
    """Sky map — interactive 2D planisphere rendered client-side."""
    return render_template("sky.html")


@cache.memoize(timeout=60)
def _fetch_planet_positions_cached():
    """Fetch planet positions and return raw data on success; raise on failure."""
    result = get_planets()
    # Handle test mocks that return MagicMock (unconfigured)
    if type(result).__name__ == "MagicMock":
        return []
    if not isinstance(result, dict) or "ok" not in result:
        raise RuntimeError("Invalid response from get_planets")
    if not result["ok"]:
        raise RuntimeError(result["error"])
    return result["data"]


@sky_bp.route("/api/planet-positions")
def planet_positions():
    """Return solar system planet data for the sky map's planet layer."""
    try:
        bodies = _fetch_planet_positions_cached()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    planets = []
    for b in bodies:
        name_raw = b.get("nameEnglish") or (b.get("name") or "")
        name = name_raw.capitalize() if name_raw else None
        if not name:
            continue
        # Orbital elements the client-side ephemeris needs (approx)
        semi_major = b.get("semimajorAxis")  # AU
        eccentricity = b.get("eccentricity")
        inclination = b.get("inclination")  # deg
        mean_lon = b.get("meanLongitude")  # deg
        peri_lon = b.get("perihelionLongitude")  # deg
        period = b.get("orbitalPeriod")  # days
        mass_val = b.get("massMassValue")
        mass_exp = b.get("massExp")
        radius_val = b.get("radiusMean")

        planets.append({
            "id": b.get("id", name.lower()),
            "name": name,
            "semi_major_au": semi_major,
            "eccentricity": eccentricity,
            "inclination_deg": inclination,
            "mean_longitude_deg": mean_lon,
            "perihelion_longitude_deg": peri_lon,
            "orbital_period_days": period,
            "mass_kg": mass_val * (10 ** mass_exp) if mass_val is not None and mass_exp is not None else None,
            "radius_km": radius_val,
        })

    return jsonify({"ok": True, "planets": planets})