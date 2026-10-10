import re
from datetime import date as _date

import requests

from app.cache import cache

ONTHISDAY_URL = "https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/events"

PEOPLE_IN_SPACE_URL = "http://api.open-notify.org/astros.json"

FIREBALL_URL = "https://ssd-api.jpl.nasa.gov/fireball.api"

REQUEST_TIMEOUT = 10

USER_AGENT = "SpaceBoard/1.0 (educational project; contact via the repository)"

# Words that mark an On This Day event as space-related. The feed is the whole
# day of history, so an event only counts when one of these appears in its text.
SPACE_KEYWORDS = (
    "space", "nasa", "apollo", "sputnik", "satellite", "orbit", "rocket",
    "launch", "soviet", "telescope", "planet", "mars", "venus", "lunar",
    "moon", "cosmonaut", "astronaut", "spacecraft", "voyager", "hubble",
    "skylab", "mercury", "gemini", "vostok", "galaxy", "nebula", "asteroid",
    "comet", "meteor", "star", "pluto", "jupiter", "saturn", "neptune",
    "uranus", "exoplanet",
)

_TAG_RE = re.compile(r"<[^>]+>")


def _ok(data):
    """Wrap a successful API response."""
    return {"ok": True, "data": data, "error": None}


def _fail(message):
    """Wrap a failed API response with a human-readable message."""
    return {"ok": False, "data": None, "error": message}


def _get(url, **kwargs):
    """GET with the User-Agent Wikimedia's policy asks for."""
    headers = kwargs.pop("headers", {})
    headers.setdefault("User-Agent", USER_AGENT)
    return requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs)


@cache.memoize(timeout=3600)
def _fetch_onthisday_cached(month_day):
    """Fetch a day's history events and return raw JSON; raise on failure."""
    response = _get(f"{ONTHISDAY_URL}/{month_day}")
    response.raise_for_status()
    return response.json()


@cache.memoize(timeout=3600)
def _fetch_people_in_space_cached():
    """Fetch who is in space right now; raise on failure."""
    response = _get(PEOPLE_IN_SPACE_URL)
    response.raise_for_status()
    return response.json()


@cache.memoize(timeout=3600)
def _fetch_fireball_cached():
    """Fetch the most recent bright fireballs; raise on failure."""
    response = _get(FIREBALL_URL, params={"limit": 1})
    response.raise_for_status()
    return response.json()


def _clean_text(text):
    """The feed's text can carry inline HTML; render it as plain prose."""
    if not isinstance(text, str):
        return ""
    return _TAG_RE.sub("", text).strip()


def _onthisday_fact(payload):
    """Turn a day's history into a fact, or None when it has no space event."""
    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        return None

    for event in events:
        if not isinstance(event, dict):
            continue
        text = event.get("text")
        if not isinstance(text, str) or not text:
            continue
        if not any(keyword in text.lower() for keyword in SPACE_KEYWORDS):
            continue

        body = _clean_text(text)
        if not body:
            continue

        year = event.get("year")
        pages = event.get("pages") if isinstance(event.get("pages"), list) else []
        page = pages[0] if pages and isinstance(pages[0], dict) else {}
        url = (page.get("content_urls") or {}).get("desktop", {}).get("page")
        if not url:
            title = page.get("normalizedtitle") or page.get("title") or ""
            url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}" if title else ""
        headline = page.get("normalizedtitle") or page.get("title") or (
            f"On this day in {year}" if year else "On this day"
        )

        return {
            "headline": headline,
            "body": f"{year} — {body}" if year else body,
            "source_label": "Wikipedia",
            "source_url": url or "https://www.wikipedia.org/",
        }
    return None


def _people_in_space_fact(payload):
    """A live roster of who is in orbit right now."""
    people = payload.get("people") if isinstance(payload, dict) else None
    if not isinstance(people, list) or not people:
        return None

    crafts = {}
    for person in people:
        if not isinstance(person, dict):
            continue
        craft = person.get("craft") or "unknown craft"
        crafts.setdefault(craft, []).append(person.get("name") or "an astronaut")

    summary = ", ".join(
        f"{len(names)} aboard the {craft}" for craft, names in sorted(crafts.items())
    )
    return {
        "headline": "Humans in space right now",
        "body": f"{payload.get('number', len(people))} people are currently in orbit: {summary}.",
        "source_label": "Open Notify",
        "source_url": "http://open-notify.org/",
    }


def _fireball_fact(payload):
    """The most recent meteor bright enough for NASA to log it."""
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        return None

    row = data[0]
    fields = payload.get("fields") if isinstance(payload.get("fields"), list) else []
    record = dict(zip(fields, row))
    when = record.get("date", "an unrecorded date")
    energy = record.get("energy")
    latitude = record.get("lat")
    longitude = record.get("lon")

    parts = [f"A bright fireball was detected on {when}"]
    if energy:
        parts.append(f"with an impact energy of {energy} kilotons of TNT")
    if latitude and longitude:
        parts.append(
            f"over {latitude}°{record.get('lat-dir', '')}, "
            f"{longitude}°{record.get('lon-dir', '')}"
        )
    return {
        "headline": "Latest bright fireball",
        "body": " ".join(parts) + ".",
        "source_label": "NASA/JPL",
        "source_url": "https://ssd.jpl.nasa.gov/tools/fireball.html",
    }


def get_daily_fact():
    """A fact for the home page that changes with the date.

    The copy is never built in: it comes from a live source every day. Space
    history for today's month/day is preferred, falling back to who is in
    orbit right now, then to the latest bright fireball — both also live and
    also interesting.

    Returns:
        dict: {"ok": bool, "data": {"headline", "body", "source_label",
               "source_url"}|None, "error": str|None}

    ``data`` is None when no source answered, so the page omits the section
    rather than substituting copy of its own.
    """
    today = _date.today()
    month_day = today.strftime("%m/%d")

    sources = (
        (_fetch_onthisday_cached, (month_day,), _onthisday_fact),
        (_fetch_people_in_space_cached, (), _people_in_space_fact),
        (_fetch_fireball_cached, (), _fireball_fact),
    )

    for fetch, args, interpret in sources:
        try:
            payload = fetch(*args)
        except requests.exceptions.Timeout:
            continue
        except requests.exceptions.HTTPError:
            continue
        except requests.exceptions.RequestException:
            continue
        except Exception:
            continue

        try:
            fact = interpret(payload)
        except Exception:
            fact = None
        if fact:
            return _ok(fact)

    return _ok(None)
