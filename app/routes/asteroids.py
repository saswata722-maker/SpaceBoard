from datetime import date, timedelta
from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.api.imagery import get_body_image
from app.api.neows import get_neo, get_neo_feed

asteroids_bp = Blueprint("asteroids", __name__, url_prefix="/asteroids")

MAX_DATE_RANGE_DAYS = 7


def _default_start():
    return date.today().isoformat()


def _default_end():
    return (date.today() + timedelta(days=MAX_DATE_RANGE_DAYS)).isoformat()


def _validate_date_range(start_date_str, end_date_str):
    """Validate that the date range is within NASA API limits (max 7 days)."""
    try:
        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)
    except ValueError:
        return False, "Invalid date format. Use YYYY-MM-DD."

    if start_date > end_date:
        return False, "Start date must be before or equal to end date."

    if (end_date - start_date).days > MAX_DATE_RANGE_DAYS:
        return False, f"Date range cannot exceed {MAX_DATE_RANGE_DAYS} days (NASA API limit)."

    return True, None


@asteroids_bp.route("/", methods=["GET"])
def index():
    """Asteroid dashboard: filterable NEO table with date range and hazard status."""
    start_date = request.args.get("start_date") or _default_start()
    end_date = request.args.get("end_date") or _default_end()
    hazardous_only = request.args.get("hazardous") == "on"

    # Validate date range
    valid, error_msg = _validate_date_range(start_date, end_date)
    if not valid:
        return render_template(
            "asteroids.html",
            neos=[],
            element_count=0,
            start_date=start_date,
            end_date=end_date,
            hazardous_only=hazardous_only,
            error=error_msg,
        )

    result = get_neo_feed(start_date, end_date)
    neos = result["data"]["neos"] if result["ok"] else []
    element_count = result["data"]["element_count"] if result["ok"] else 0

    if result["ok"] and hazardous_only:
        neos = [n for n in neos if n.get("is_potentially_hazardous_asteroid")]
        element_count = len(neos)  # Update count to reflect filtered results

    return render_template(
        "asteroids.html",
        neos=neos,
        element_count=element_count,
        start_date=start_date,
        end_date=end_date,
        hazardous_only=hazardous_only,
        error=result["error"],
    )


@asteroids_bp.route("/<neo_id>")
def neo_detail(neo_id):
    """Asteroid detail page — shows full NEO data + all close approaches."""
    result = get_neo(neo_id)
    if not result["ok"] or result["data"] is None:
        flash(f"Could not load details for asteroid {neo_id}. Please try again.", "error")
        return redirect(url_for("asteroids.index"))

    return render_template(
        "asteroid_detail.html",
        neo=result["data"],
        neo_id=neo_id,
        body_image=get_body_image(result["data"].get("name"))["data"],
    )