import requests

from flask import current_app

from app.cache import cache

APOD_URL = "https://api.nasa.gov/planetary/apod"


def _ok(data):
    """Wrap a successful API response."""
    return {"ok": True, "data": data, "error": None}


def _fail(message):
    """Wrap a failed API response with a human-readable message."""
    return {"ok": False, "data": None, "error": message}


@cache.memoize(timeout=3600)
def get_apod(date=None):
    """Fetch NASA's Astronomy Picture of the Day.

    Args:
        date: Optional date string in YYYY-MM-DD format. If None,
              fetches today's APOD.

    Returns:
        dict: {"ok": bool, "data": dict|None, "error": str|None}
    """
    api_key = current_app.config["NASA_API_KEY"]
    params = {"api_key": api_key, "thumbs": True}
    if date:
        params["date"] = date

    try:
        response = requests.get(APOD_URL, params=params, timeout=10)
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
