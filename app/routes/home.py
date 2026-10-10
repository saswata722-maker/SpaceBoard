from flask import Blueprint, render_template

from app.api.apod import get_apod
from app.api.spacefacts import get_daily_fact

home_bp = Blueprint("home", __name__)

# Same star mark the templates declare via <link rel="icon">. Browsers also
# probe /favicon.ico directly (bookmarks, older engines), so answer that too
# instead of leaving a 404 in the log.
FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    '<polygon points="50,5 61,35 95,35 68,57 79,90 50,70 21,90 32,57 5,35 39,35" '
    'fill="#fbbf24"/></svg>'
)


@home_bp.route("/favicon.ico")
def favicon():
    """Serve the star favicon for direct /favicon.ico requests."""
    return FAVICON_SVG, 200, {"Content-Type": "image/svg+xml"}


@home_bp.route("/")
def index():
    """Home page: the day's fact and media, both live, neither built in."""
    media = get_apod()
    fact = get_daily_fact()
    return render_template(
        "home.html",
        apod=media["data"],
        error=media["error"],
        fact=fact["data"],
    )
