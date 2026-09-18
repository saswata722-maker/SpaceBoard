import base64
from io import BytesIO

from flask import Blueprint, render_template

from app.api.apod import get_apod

stars_bp = Blueprint("stars", __name__, url_prefix="/stars")


# Inline SVG favicon as a data URI — a small star icon.
# Used to satisfy browser favicon requests without a separate file.
def _star_favicon_svg():
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<polygon points="50,5 61,35 95,35 68,57 79,90 50,70 21,90 32,57 5,35 39,35" '
        'fill="#fbbf24"/></svg>'
    )


@stars_bp.route("/favicon.ico")
def favicon():
    """Serve a small star favicon to prevent 404 noise."""
    svg = _star_favicon_svg()
    encoded = base64.b64encode(svg.encode()).decode()
    return (
        f'<html><head><link rel="icon" href="data:image/svg+xml;base64,{encoded}">'
        f"</head><body></body></html>",
        200,
    )


@stars_bp.route("/", methods=["GET"])
def index():
    """Stars section — APOD gallery and stellar imagery."""
    from datetime import date, timedelta

    end_date = date.today()
    start_date = end_date - timedelta(days=7)

    # Fetch multiple APODs for the gallery
    from app.api.apod import get_apod as fetch_apod

    apods = []
    current = start_date
    while current <= end_date:
        result = fetch_apod(current.isoformat())
        if result["ok"] and result["data"]:
            apods.append(result["data"])
        current += timedelta(days=1)

    return render_template("stars.html", apods=apods)
