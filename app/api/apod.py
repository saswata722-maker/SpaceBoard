import requests
from datetime import date as _date, timedelta as _timedelta

from flask import current_app

from app.cache import cache

APOD_URL = "https://api.nasa.gov/planetary/apod"


def _ok(data):
    """Wrap a successful API response."""
    return {"ok": True, "data": data, "error": None}


def _fail(message):
    """Wrap a failed API response with a human-readable message."""
    return {"ok": False, "data": None, "error": message}


def _fetch_apod(api_key, date_str):
    """Fire a single APOD request and return the ``requests.Response``."""
    return requests.get(
        APOD_URL,
        params={"api_key": api_key, "date": date_str, "thumbs": True},
        timeout=15,
    )


@cache.memoize(timeout=3600)
def get_apod(date=None):
    """Fetch NASA's Astronomy Picture of the Day.

    Args:
        date: Optional date string in YYYY-MM-DD format. If *None*,
              today's date is sent (the upstream API returns HTTP 500
              when no ``date`` parameter is present).

    Returns:
        dict: {"ok": bool, "data": dict|None, "error": str|None}
    """
    api_key = current_app.config["NASA_API_KEY"]
    target = date or _date.today().isoformat()

    try:
        response = _fetch_apod(api_key, target)

        # If today's picture isn't published yet, fall back one day.
        if response.status_code >= 500 and date is None:
            yesterday = (_date.today() - _timedelta(days=1)).isoformat()
            response = _fetch_apod(api_key, yesterday)

        response.raise_for_status()
        return _ok(response.json())
    except requests.exceptions.Timeout:
        return _fail("The request to NASA's APOD API timed out. Please try again.")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            return _fail("NASA API rate limit exceeded. Please wait and try again.")
        return _fail(f"NASA APOD API returned an error (HTTP {e.response.status_code}).")
    except requests.exceptions.RequestException as e:
        return _fail(f"Could not reach NASA's APOD API: {str(e)}")
    except Exception as e:
        return _fail(f"Unexpected error fetching APOD data: {str(e)}")
