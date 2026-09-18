from datetime import date, timedelta

from flask import Blueprint, render_template, request

from app.api.neows import get_neo_feed

asteroids_bp = Blueprint("asteroids", __name__, url_prefix="/asteroids")


def _default_start():
    return date.today().isoformat()


def _default_end():
    return (date.today() + timedelta(days=7)).isoformat()


@asteroids_bp.route("/", methods=["GET"])
def index():
    """Asteroid dashboard: filterable NEO table with date range and hazard status."""
    start_date = request.args.get("start_date") or _default_start()
    end_date = request.args.get("end_date") or _default_end()
    hazardous_only = request.args.get("hazardous") == "on"

    result = get_neo_feed(start_date, end_date)
    neos = result["data"]["neos"] if result["ok"] else []
    element_count = result["data"]["element_count"] if result["ok"] else 0

    if result["ok"] and hazardous_only:
        neos = [n for n in neos if n.get("is_potentially_hazardous_asteroid")]

    return render_template(
        "asteroids.html",
        neos=neos,
        element_count=element_count,
        start_date=start_date,
        end_date=end_date,
        hazardous_only=hazardous_only,
        error=result["error"],
    )
