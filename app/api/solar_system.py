import requests

from flask import current_app

from app.cache import cache

SOLAR_SYSTEM_BASE_URL = "https://api.le-systeme-solaire.net/rest/bodies"


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
        params = {"data": "id,nameEnglish,name,massMassValue,massExp,radiusMean,radiusExp,gravity,density,escape,semimajorAxis,perihelion,aphelion,orbitalPeriod,inclination,eccentricity,discoveredBy,discoveryDate,moons,moonsMoon"}
        response = requests.get(SOLAR_SYSTEM_BASE_URL, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
        bodies = payload.get("bodies", [])

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
def get_body(body_id):
    """Fetch a single solar system body by its ID.

    Args:
        body_id: The body's unique identifier (e.g., "earth", "mars").

    Returns:
        dict: {"ok": bool, "data": dict|None, "error": str|None}
    """
    try:
        url = f"{SOLAR_SYSTEM_BASE_URL}/{body_id}"
        response = requests.get(url, timeout=15)
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
