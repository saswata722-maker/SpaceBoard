from flask import Blueprint, render_template

from app.api.apod import get_apod

stars_bp = Blueprint("stars", __name__, url_prefix="/stars")


@stars_bp.route("/", methods=["GET"])
def index():
    """Stars section — APOD gallery and stellar imagery."""
    from datetime import date, timedelta

    end_date = date.today()
    start_date = end_date - timedelta(days=7)

    # Fetch multiple APODs for the gallery.
    # Call the module-level name deliberately: tests patch
    # `app.routes.stars.get_apod`, and a function-local re-import would bypass
    # the mock and hit NASA's real API on every test run.
    apods = []
    current = start_date
    while current <= end_date:
        result = get_apod(current.isoformat())
        if result["ok"] and result["data"]:
            apods.append(result["data"])
        current += timedelta(days=1)

    return render_template("stars.html", apods=apods)
