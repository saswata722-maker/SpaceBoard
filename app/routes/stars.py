from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from flask import Blueprint, current_app, render_template

from app.api.apod import get_apod

stars_bp = Blueprint("stars", __name__, url_prefix="/stars")

GALLERY_DAYS = 8


@stars_bp.route("/", methods=["GET"])
def index():
    """Stars section — APOD gallery and stellar imagery."""
    end_date = date.today()
    start_date = end_date - timedelta(days=GALLERY_DAYS - 1)
    dates = [(start_date + timedelta(days=offset)).isoformat()
             for offset in range(GALLERY_DAYS)]

    # Fetch concurrently (~3 s instead of ~22 s sequentially). Worker threads
    # need their own application context: Flask's context is thread-local, so
    # get_apod()'s `current_app.config` lookup would raise
    # "Working outside of application context" without this.
    # The module-level `get_apod` name is used deliberately so tests can patch
    # `app.routes.stars.get_apod`.
    app = current_app._get_current_object()

    def _fetch(day):
        with app.app_context():
            result = get_apod(day)
        return result["data"] if result["ok"] and result["data"] else None

    with ThreadPoolExecutor(max_workers=GALLERY_DAYS) as pool:
        # pool.map preserves the input order, so the gallery stays chronological.
        apods = [apod for apod in pool.map(_fetch, dates) if apod is not None]

    return render_template("stars.html", apods=apods)
