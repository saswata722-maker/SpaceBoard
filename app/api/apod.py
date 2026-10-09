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


def _fetch_apod_raw(api_key, date_str):
    """Fire a single APOD request and return the ``requests.Response``."""
    return requests.get(
        APOD_URL,
        params={"api_key": api_key, "date": date_str, "thumbs": True},
        timeout=15,
    )


@cache.memoize(timeout=3600)
def _fetch_apod_with_fallback_cached(api_key, date_str, is_today):
    """Fetch APOD with fallback for today's date; return raw JSON on success; raise on failure."""
    # First try the requested date
    response = _fetch_apod_raw(api_key, date_str)
    if response.status_code >= 400:
        # If it's today and we got a 5xx, try yesterday (but don't cache the failure)
        if is_today and response.status_code >= 500:
            yesterday = (_date.today() - _timedelta(days=1)).isoformat()
            response = _fetch_apod_raw(api_key, yesterday)
            if response.status_code >= 400:
                response.raise_for_status()
        else:
            response.raise_for_status()
    return response.json()


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
    is_today = date is None

    try:
        data = _fetch_apod_with_fallback_cached(api_key, target, is_today)
        return _ok(data)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            return _fail("NASA API rate limit exceeded. Please wait and try again.")
        return _fail(f"NASA APOD API returned an error (HTTP {e.response.status_code if e.response else 'unknown'}).")
    except requests.exceptions.Timeout:
        return _fail("The request to NASA's APOD API timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        return _fail(f"Could not reach NASA's APOD API: {str(e)}")
    except Exception as e:
        return _fail(f"Unexpected error fetching APOD data: {str(e)}")