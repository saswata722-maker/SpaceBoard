from flask import Blueprint, render_template

from app.api.apod import get_apod

home_bp = Blueprint("home", __name__)


@home_bp.route("/")
def index():
    """Home page displaying NASA's Astronomy Picture of the Day."""
    result = get_apod()
    return render_template("home.html", apod=result["data"], error=result["error"])
