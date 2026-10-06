from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from flask import Blueprint, current_app, render_template, request

from app.api.apod import get_apod

stars_bp = Blueprint("stars", __name__, url_prefix="/stars")

DEFAULT_GALLERY_DAYS = 8
MAX_GALLERY_DAYS = 30


def _parse_date(value, fallback):
    """Parse an ISO date, ignoring anything unusable."""
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return fallback


def _gallery_window(requested_start, requested_end, today):
    """Resolve the gallery window.

    Defaults to the last DEFAULT_GALLERY_DAYS days. The window is never empty,
    never runs past today (APOD has no future entries) and never spans more than
    MAX_GALLERY_DAYS, which also bounds how many upstream calls a request makes.
    """
    end_date = _parse_date(requested_end, today)
    start_date = _parse_date(
        requested_start, end_date - timedelta(days=DEFAULT_GALLERY_DAYS - 1)
    )
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    if end_date > today:
        end_date = today
        if start_date > end_date:
            start_date = end_date
    if (end_date - start_date).days + 1 > MAX_GALLERY_DAYS:
        start_date = end_date - timedelta(days=MAX_GALLERY_DAYS - 1)
    return start_date, end_date


@stars_bp.route("/", methods=["GET"])
def index():
    """Stars section — APOD gallery with a date-range picker and paging."""
    today = date.today()
    start_date, end_date = _gallery_window(
        request.args.get("start"), request.args.get("end"), today
    )
    span = (end_date - start_date).days + 1
    dates = [(start_date + timedelta(days=offset)).isoformat()
             for offset in range(span)]

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

    with ThreadPoolExecutor(max_workers=min(span, 10)) as pool:
        # pool.map preserves the input order, so the gallery stays chronological.
        apods = [apod for apod in pool.map(_fetch, dates) if apod is not None]

    # Paging shifts the whole window by its own length.
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span - 1)
    next_start = end_date + timedelta(days=1)
    next_end = min(next_start + timedelta(days=span - 1), today)

    return render_template(
        "stars.html",
        apods=apods,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        span=span,
        today=today.isoformat(),
        prev_start=prev_start.isoformat(),
        prev_end=prev_end.isoformat(),
        next_start=next_start.isoformat(),
        next_end=next_end.isoformat(),
        has_next=end_date < today,
    )
