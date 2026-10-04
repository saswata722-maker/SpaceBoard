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
def get_exoplanets(search=None, limit=200):
    """Fetch confirmed exoplanets from the NASA Exoplanet Archive.

    Args:
        search: Optional text to filter by planet or host-star name.
        limit: Maximum number of results (default 200).

    Returns:
        dict: {"ok": bool, "data": list|None, "error": str|None}
    """
    try:
        if search and search.strip():
            where = (
                f"where default_flag = 1 and {_search_condition(search.strip())}"
            )
        else:
            where = "where default_flag = 1"

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
