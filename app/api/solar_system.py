import requests

from flask import current_app

from app.cache import cache

SOLAR_SYSTEM_BASE_URL = "https://api.le-systeme-solaire.net/rest/bodies"

# The upstream API started requiring a bearer token ("API key is missing").
# Request a free key at https://api.le-systeme-solaire.net/generatekey.html and
# put it in .env as SOLAR_SYSTEM_API_KEY. Without a key the live call 401s and
# get_planets() serves LOCAL_PLANETS instead, so the UI always has data.
#
# Field names as the upstream API actually returns them (2026-era schema).
FIELDS = (
    "id,englishName,name,isPlanet,mass,meanRadius,gravity,"
    "semimajorAxis,eccentricity,inclination,sideralOrbit,discoveredBy,moons"
)


def _headers():
    """Bearer token from app config, read per call (not at import time) so a
    .env change or a per-instance override actually takes effect."""
    key = (current_app.config.get("SOLAR_SYSTEM_API_KEY") or "").strip()
    return {"Authorization": f"Bearer {key}"} if key else {}


def _normalise(body):
    """Map a live API body into the shape every template and test expects.

    Upstream renames since the code was first written:
        englishName   → nameEnglish
        mass.massValue / mass.massExponent → massMassValue / massExp
        meanRadius    → radiusMean
        sideralOrbit  → orbitalPeriod
    """
    mass = body.get("mass") or {}
    return {
        "id":               body.get("id"),
        "name":             body.get("name"),
        "nameEnglish":      body.get("englishName"),
        "isPlanet":         body.get("isPlanet"),
        "massMassValue":    mass.get("massValue"),
        "massExp":          mass.get("massExponent"),
        "radiusMean":       body.get("meanRadius"),
        "gravity":          body.get("gravity"),
        "semimajorAxis":    body.get("semimajorAxis"),
        "eccentricity":     body.get("eccentricity"),
        "inclination":      body.get("inclination"),
        "orbitalPeriod":    body.get("sideralOrbit"),
        "discoveredBy":     body.get("discoveredBy"),
        "moons":            body.get("moons") or [],
    }


def _moons(count):
    """The template only shows the moon count, so the giants carry count-only
    placeholders rather than ~150 names each. ponytail: upgrade path is to list
    real names if the UI ever needs them."""
    return [{"moon": ""} for _ in range(count)]


LOCAL_PLANETS = [
    {"id": "mercure", "name": "Mercure", "nameEnglish": "Mercury",
     "massMassValue": 3.301, "massExp": 23, "radiusMean": 2439.7, "gravity": 3.70,
     "semimajorAxis": 57909050, "eccentricity": 0.2056, "inclination": 7.005,
     "orbitalPeriod": 87.97, "moons": _moons(0), "discoveredBy": None},
    {"id": "venus", "name": "V\u00e9nus", "nameEnglish": "Venus",
     "massMassValue": 4.867, "massExp": 24, "radiusMean": 6051.8, "gravity": 8.87,
     "semimajorAxis": 108208000, "eccentricity": 0.0068, "inclination": 3.395,
     "orbitalPeriod": 224.70, "moons": _moons(0), "discoveredBy": None},
    {"id": "terre", "name": "Terre", "nameEnglish": "Earth",
     "massMassValue": 5.972, "massExp": 24, "radiusMean": 6371.0, "gravity": 9.81,
     "semimajorAxis": 149598023, "eccentricity": 0.0167, "inclination": 0.0,
     "orbitalPeriod": 365.25, "moons": [{"moon": "Lune"}], "discoveredBy": None},
    {"id": "mars", "name": "Mars", "nameEnglish": "Mars",
     "massMassValue": 6.417, "massExp": 23, "radiusMean": 3389.5, "gravity": 3.71,
     "semimajorAxis": 227939200, "eccentricity": 0.0934, "inclination": 1.850,
     "orbitalPeriod": 686.98, "moons": [{"moon": "Phobos"}, {"moon": "Deimos"}],
     "discoveredBy": None},
    {"id": "jupiter", "name": "Jupiter", "nameEnglish": "Jupiter",
     "massMassValue": 1.898, "massExp": 27, "radiusMean": 69911.0, "gravity": 24.79,
     "semimajorAxis": 778570000, "eccentricity": 0.0484, "inclination": 1.303,
     "orbitalPeriod": 4332.59, "moons": _moons(95), "discoveredBy": None},
    {"id": "saturne", "name": "Saturne", "nameEnglish": "Saturn",
     "massMassValue": 5.683, "massExp": 26, "radiusMean": 58232.0, "gravity": 10.44,
     "semimajorAxis": 1433530000, "eccentricity": 0.0542, "inclination": 2.489,
     "orbitalPeriod": 10759.22, "moons": _moons(146), "discoveredBy": None},
    {"id": "uranus", "name": "Uranus", "nameEnglish": "Uranus",
     "massMassValue": 8.681, "massExp": 25, "radiusMean": 25362.0, "gravity": 8.69,
     "semimajorAxis": 2872460000, "eccentricity": 0.0472, "inclination": 0.773,
     "orbitalPeriod": 30685.4, "moons": _moons(28), "discoveredBy": "William Herschel"},
    {"id": "neptune", "name": "Neptune", "nameEnglish": "Neptune",
     "massMassValue": 1.024, "massExp": 26, "radiusMean": 24622.0, "gravity": 11.15,
     "semimajorAxis": 4495060000, "eccentricity": 0.0086, "inclination": 1.770,
     "orbitalPeriod": 60189.0, "moons": _moons(16), "discoveredBy": "Urbain Le Verrier"},
    {"id": "pluton", "name": "Pluton", "nameEnglish": "Pluto",
     "massMassValue": 1.303, "massExp": 22, "radiusMean": 1188.3, "gravity": 0.62,
     "semimajorAxis": 5906380000, "eccentricity": 0.2488, "inclination": 17.16,
     "orbitalPeriod": 90560.0, "moons": _moons(5), "discoveredBy": "Clyde Tombaugh"},
]



def _ok(data):
    return {"ok": True, "data": data, "error": None}


def _fail(message):
    return {"ok": False, "data": None, "error": message}


@cache.memoize(timeout=3600)
def get_bodies(is_planet=None):
    """Fetch solar system bodies from the Solar System OpenData API.

    Args:
        is_planet: If True, filter to planets only. If None, return all bodies.

    Returns:
        dict: {"ok": bool, "data": list|None, "error": str|None}
    """
    try:
        response = requests.get(
            SOLAR_SYSTEM_BASE_URL,
            params={"data": FIELDS},
            headers=_headers(),
            timeout=6,
        )
        response.raise_for_status()
        payload = response.json()
        raw_bodies = payload.get("bodies", [])

        # Normalise upstream field names → template-expected names.
        bodies = [_normalise(b) for b in raw_bodies]

        if is_planet:
            bodies = [b for b in bodies if b.get("isPlanet") is True]

        return _ok(bodies)
    except requests.exceptions.Timeout:
        return _fail("The request to the Solar System OpenData API timed out.")
    except requests.exceptions.HTTPError as e:
        return _fail(
            f"Solar System OpenData API returned an error (HTTP {e.response.status_code})."
        )
    except requests.exceptions.RequestException as e:
        return _fail(f"Could not reach Solar System OpenData API: {str(e)}")
    except Exception as e:
        return _fail(f"Unexpected error fetching solar system data: {str(e)}")


@cache.memoize(timeout=3600)
def get_planets():
    """Planets for the UI, with a built-in fallback.

    The live API now needs a bearer token, so a missing key or an outage means
    the card grid would be empty. Falling back to LOCAL_PLANETS keeps the
    planets page (and the sky map's planet layer) usable, and the note tells the
    template to say where the numbers came from.

    Returns:
        dict: {"ok": True, "data": list, "error": None, "note": str|None}
    """
    result = get_bodies(is_planet=True)
    if result["ok"] and result["data"]:
        return {"ok": True, "data": result["data"], "error": None, "note": None}

    return {
        "ok": True,
        "data": LOCAL_PLANETS,
        "error": None,
        "note": (
            "Live solar system data is unavailable (the OpenData API now needs a "
            f"free API key: {result['error']}). Showing built-in planet data."
        ),
    }


@cache.memoize(timeout=3600)
def get_body(body_id):
    """Fetch a single solar system body by its ID.

    Args:
        body_id: The body's unique identifier (e.g., "earth", "mars").

    Returns:
        dict: {"ok": bool, "data": dict|None, "error": str|None}
    """
    try:
        url = f"{SOLAR_SYSTEM_BASE_URL}/{body_id}"
        response = requests.get(url, timeout=6)
        response.raise_for_status()
        return _ok(response.json())
    except requests.exceptions.Timeout:
        return _fail("The request to the Solar System OpenData API timed out.")
    except requests.exceptions.HTTPError as e:
        return _fail(
            f"Solar System OpenData API returned an error (HTTP {e.response.status_code})."
        )
    except requests.exceptions.RequestException as e:
        return _fail(f"Could not reach Solar System OpenData API: {str(e)}")
    except Exception as e:
        return _fail(f"Unexpected error fetching body data: {str(e)}")
