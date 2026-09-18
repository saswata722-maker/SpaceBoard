import requests

from flask import current_app

from app.cache import cache

NEOWS_FEED_URL = "https://api.nasa.gov/neo/rest/v1/feed"


def _ok(data):
    """Wrap a successful API response."""
    return {"ok": True, "data": data, "error": None}


def _fail(message):
    """Wrap a failed API response with a human-readable message."""
    return {"ok": False, "data": None, "error": message}


def _flatten_neos(near_earth_objects):
    """Flatten the date-nested NeoWs feed into a single list sorted by approach date."""
    neos = []
    for _date_str, date_neos in near_earth_objects.items():
        for neo in date_neos:
            neos.append(neo)

    neos.sort(
        key=lambda n: n.get("close_approach_data", [{}])[0].get(
            "close_approach_date", ""
        )
    )
    return neos


@cache.memoize(timeout=3600)
def get_neo_feed(start_date, end_date):
    """Fetch near-Earth objects for a date range.

    NASA's feed endpoint nests NEOs by date. This function flattens
    them into a single list sorted by close-approach date.

    Args:
        start_date: Start date string in YYYY-MM-DD format.
        end_date: End date string in YYYY-MM-DD format (max 7 days
                  after start_date per NASA API rules).

    Returns:
        dict: {"ok": bool, "data": dict|None, "error": str|None}
              data contains: neos (list), element_count (int),
              start_date, end_date
    """
    api_key = current_app.config["NASA_API_KEY"]
    params = {
        "api_key": api_key,
        "start_date": start_date,
        "end_date": end_date,
    }

    try:
        response = requests.get(NEOWS_FEED_URL, params=params, timeout=10)
        response.raise_for_status()
        payload = response.json()
        neos = _flatten_neos(payload.get("near_earth_objects", {}))
        return _ok(
            {
                "neos": neos,
                "element_count": payload.get("element_count", 0),
                "start_date": start_date,
                "end_date": end_date,
            }
        )
    except requests.exceptions.Timeout:
        return _fail("The request to NASA's NeoWs API timed out. Please try again.")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            return _fail("NASA API rate limit exceeded. Please wait and try again.")
        return _fail(
            f"NASA NeoWs API returned an error (HTTP {e.response.status_code})."
        )
    except requests.exceptions.RequestException as e:
        return _fail(f"Could not reach NASA's NeoWs API: {str(e)}")
    except Exception as e:
        return _fail(f"Unexpected error fetching NeoWs data: {str(e)}")
