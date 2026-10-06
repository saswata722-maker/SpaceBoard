import requests

from flask import current_app

from app.cache import cache

EXOPLANET_TAP_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"

# Column list shared by every query.  The limit is applied via ADQL's
# ``select top N`` (the Archive's Oracle backend rejects ``LIMIT``).
_COLUMNS = (
    "pl_name, hostname, sy_snum, sy_pnum, discoverymethod, "
    "disc_year, pl_orbper, pl_orbsmax, pl_rade, pl_radj, pl_bmasse, "
    "pl_bmassj, pl_eqt, pl_dens, st_spectype"
)

# Every discovery method present in the Archive's default-planets table,
# ordered by how many planets it discovered. Doubles as the dropdown vocabulary
# and as the injection guard: a filter is only applied when it is a known value.
DISCOVERY_METHODS = (
    "Transit",
    "Radial Velocity",
    "Microlensing",
    "Imaging",
    "Transit Timing Variations",
    "Eclipse Timing Variations",
    "Orbital Brightness Modulation",
    "Pulsar Timing",
    "Astrometry",
    "Disk Kinematics",
)


def _ok(data):
    return {"ok": True, "data": data, "error": None}


def _fail(message):
    return {"ok": False, "data": None, "error": message}


def _search_condition(search_term):
    """Build a SQL WHERE clause fragment for text search across name and host."""
    term = search_term.replace("'", "''")  # basic SQL injection guard
    return (
        f"(pl_name like '%{term}%' or hostname like '%{term}%')"
    )


@cache.memoize(timeout=3600)
def get_exoplanets(search=None, discovery=None, limit=200):
    """Fetch confirmed exoplanets from the NASA Exoplanet Archive.

    Args:
        search: Optional text to filter by planet or host-star name.
        discovery: Optional discovery method; ignored unless it is one of
            DISCOVERY_METHODS (which is also the SQL-injection guard).
        limit: Maximum number of results (default 200).

    Returns:
        dict: {"ok": bool, "data": list|None, "error": str|None}
    """
    try:
        conditions = ["default_flag = 1"]
        if search and search.strip():
            conditions.append(_search_condition(search.strip()))
        if discovery and discovery.strip() in DISCOVERY_METHODS:
            conditions.append(f"discoverymethod = '{discovery.strip()}'")

        where = "where " + " and ".join(conditions)
        query = f"select top {limit} {_COLUMNS} from ps {where}"

        params = {"query": query, "format": "json"}
        response = requests.get(EXOPLANET_TAP_URL, params=params, timeout=20)
        response.raise_for_status()

        data = response.json()
        if not isinstance(data, list):
            return _fail("Unexpected response format from Exoplanet Archive.")

        return _ok(data)
    except requests.exceptions.Timeout:
        return _fail("The request to the NASA Exoplanet Archive timed out.")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            return _fail("Exoplanet Archive rate limit exceeded. Please wait and try again.")
        return _fail(
            f"Exoplanet Archive returned an error (HTTP {e.response.status_code})."
        )
    except requests.exceptions.RequestException as e:
        return _fail(f"Could not reach NASA Exoplanet Archive: {str(e)}")
    except Exception as e:
        return _fail(f"Unexpected error fetching exoplanet data: {str(e)}")
