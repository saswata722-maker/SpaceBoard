from flask import Blueprint, render_template, request

from app.api.exoplanets import get_exoplanets
from app.api.solar_system import get_bodies

planets_bp = Blueprint("planets", __name__, url_prefix="/planets")


@planets_bp.route("/", methods=["GET"])
def index():
    """Planets section — solar system planets + searchable exoplanets."""
    search = request.args.get("search", "").strip()

    # Solar system planets
    ss_result = get_bodies(is_planet=True)
    solar_planets = ss_result["data"] if ss_result["ok"] else []
    ss_error = ss_result["error"]

    # Exoplanets (only fetch if search is provided or default load)
    exo_result = get_exoplanets(search=search if search else None)
    exoplanets = exo_result["data"] if exo_result["ok"] else []
    exo_error = exo_result["error"]

    return render_template(
        "planets.html",
        solar_planets=solar_planets,
        exoplanets=exoplanets,
        search=search,
        ss_error=ss_error,
        exo_error=exo_error,
    )
