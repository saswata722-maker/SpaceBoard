import requests
from datetime import date as _date, timedelta as _timedelta

from flask import current_app

from app.api.images import get_fallback_image
from app.cache import cache

APOD_URL = "https://api.nasa.gov/planetary/apod"

SECONDARY_PROVIDER = "nasa_image_library"


def _ok(data):
    """Wrap a successful API response."""
    return {"ok": True, "data": data, "error": None}


def _fail(message):
    """Wrap a failed API response with a human-readable message."""
    return {"ok": False, "data": None, "error": message}


def _validate_apod_payload(data):
    """A usable APOD record is a dict with a non-empty ``url`` and a known
    ``media_type``. Anything else — ``{}``, ``null``, or a record missing
    those fields — fails structural validation and triggers failover.

    Also rejects the NASA placeholder image that the API returns when the
    actual APOD isn't available yet.
    """
    if not isinstance(data, dict):
        return False
    url = data.get("url", "")
    title = data.get("title", "")
    # Reject the placeholder NASA logo that APOD returns for unavailable dates
    if "nasa-logo" in url.lower() or title == "NASA Science":
        return False
    return bool(url) and data.get("media_type") in ("image", "video")


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


def _fetch_primary(date=None):
    """Fetch from the primary APOD endpoint.

    Returns:
        tuple: ``(data, None)`` on success, or ``(None, message)`` where
        *message* is both the human-readable error the page shows when both
        providers are down and the failover trigger reason logged at WARNING.
    """
    api_key = current_app.config["NASA_API_KEY"]
    target = date or _date.today().isoformat()
    is_today = date is None

    try:
        data = _fetch_apod_with_fallback_cached(api_key, target, is_today)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            return None, "NASA API rate limit exceeded. Please wait and try again."
        status = e.response.status_code if e.response is not None else "unknown"
        return None, f"NASA APOD API returned an error (HTTP {status})."
    except requests.exceptions.Timeout:
        return None, "The request to NASA's APOD API timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return None, f"Could not reach NASA's APOD API: {str(e)}"
    except Exception as e:
        return None, f"Unexpected error fetching APOD data: {str(e)}"

    if not _validate_apod_payload(data):
        return None, f"APOD payload failed structural validation: {data!r}"

    return data, None


def get_apod(date=None):
    """Fetch NASA's Astronomy Picture of the Day.

    Args:
        date: Optional date string in YYYY-MM-DD format. If *None*,
              today's date is sent (the upstream API returns HTTP 500
              when no ``date`` parameter is present).

    Returns:
        dict: {"ok": bool, "data": dict|None, "error": str|None}

    When the primary endpoint cannot supply usable data — transport error,
    timeout, HTTP 4xx/5xx/429, or a payload that fails structural validation
    including an empty or null result — the request fails over to the NASA
    Image and Video Library. The secondary is only ever consulted after a
    primary failure, never in parallel, and its result carries its own
    attribution and ``source`` so the media is never mislabelled as APOD.
    If both providers fail, the primary failure message is returned so the
    page keeps its existing "Data Unavailable" state.
    """
    data, primary_error = _fetch_primary(date)
    if primary_error is None:
        return _ok(data)

    current_app.logger.warning(
        "APOD failover: trigger=%s provider=%s", primary_error, SECONDARY_PROVIDER
    )
    fallback = get_fallback_image()
    if fallback["ok"] and fallback["data"]:
        return _ok(fallback["data"])
    return _fail(primary_error)