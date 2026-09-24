from flask import Blueprint, render_template, request

from app.api.exoplanets import get_exoplanets
from app.api.solar_system import get_planets

planets_bp = Blueprint("planets", __name__, url_prefix="/planets")


@planets_bp.route("/", methods=["GET"])
def index():
    """Planets section — solar system planets + searchable exoplanets."""
    search = request.args.get("search", "").strip()

    # Solar system planets (live API, or built-in data when it is unavailable)
    ss_result = get_planets()
    solar_planets = ss_result["data"]
    ss_note = ss_result.get("note")

    # Exoplanets (only fetch if search is provided or default load)
    exo_result = get_exoplanets(search=search if search else None)
    exoplanets = exo_result["data"] if exo_result["ok"] else []
    exo_error = exo_result["error"]

    return render_template(
        "planets.html",
        solar_planets=solar_planets,
        ss_note=ss_note,
        exoplanets=exoplanets,
        search=search,
        exo_error=exo_error,
    )
