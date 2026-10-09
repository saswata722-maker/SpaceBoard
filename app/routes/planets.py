from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.api.exoplanets import DISCOVERY_METHODS, get_exoplanet, get_exoplanets
from app.api.solar_system import get_body, get_planets

planets_bp = Blueprint("planets", __name__, url_prefix="/planets")


@planets_bp.route("/", methods=["GET"])
def index():
    """Planets section — solar system planets + searchable exoplanets."""
    search = request.args.get("search", "").strip()
    method = request.args.get("method", "").strip()

    # Solar system planets (live API, or built-in data when it is unavailable)
    ss_result = get_planets()
    solar_planets = ss_result["data"]
    ss_note = ss_result.get("note")

    # Exoplanets (search + discovery-method filter; the route enforces the
    # whitelist so unknown methods never reach the SQL).
    if method and method not in DISCOVERY_METHODS:
        method = ""
    exo_result = get_exoplanets(
        search=search if search else None,
        discovery=method if method else None,
    )
    exoplanets = exo_result["data"] if exo_result["ok"] else []
    exo_error = exo_result["error"]

    return render_template(
        "planets.html",
        solar_planets=solar_planets,
        ss_note=ss_note,
        exoplanets=exoplanets,
        search=search,
        methods=DISCOVERY_METHODS,
        selected_method=method if method in DISCOVERY_METHODS else "",
        exo_error=exo_error,
    )


@planets_bp.route("/<body_id>")
def planet_detail(body_id):
    """Solar system planet detail page — shows all fields + moon list."""
    result = get_body(body_id)
    if not result["ok"] or result["data"] is None:
        flash(f"Could not load details for {body_id}. Please try again.", "error")
        return redirect(url_for("planets.index"))

    return render_template(
        "planet_detail.html",
        planet=result["data"],
        body_id=body_id,
    )


@planets_bp.route("/exoplanet/<pl_name>")
def exoplanet_detail(pl_name):
    """Exoplanet detail page — shows all columns from the archive."""
    result = get_exoplanet(pl_name)
    if not result["ok"] or result["data"] is None:
        flash(f"Could not load details for {pl_name}. Please try again.", "error")
        return redirect(url_for("planets.index"))

    return render_template(
        "exoplanet_detail.html",
        planet=result["data"],
        pl_name=pl_name,
    )