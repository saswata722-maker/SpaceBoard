from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import HTTPError, Timeout

from app.api.exoplanets import get_exoplanets


def _mock_response(json_data, status_code=200):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        mock.raise_for_status.side_effect = HTTPError(response=mock)
    return mock


def _app():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app


SAMPLE_EXOPLANETS = [
    {
        "pl_name": "Kepler-22 b",
        "hostname": "Kepler-22",
        "sy_snum": 1,
        "sy_pnum": 1,
        "discoverymethod": "Transit",
        "disc_year": 2011,
        "pl_orbper": 289.86,
        "pl_orbsmax": 0.849,
        "pl_rade": 2.38,
        "pl_radj": 0.212,
        "pl_bmasse": 9.1,
        "pl_bmassj": 0.029,
        "pl_eqt": 279.0,
        "pl_dens": 2.4,
        "st_spectype": "G5V",
    },
    {
        "pl_name": "TRAPPIST-1e",
        "hostname": "TRAPPIST-1",
        "sy_snum": 1,
        "sy_pnum": 7,
        "discoverymethod": "Transit",
        "disc_year": 2017,
        "pl_orbper": 6.1,
        "pl_orbsmax": 0.029,
        "pl_rade": 0.91,
        "pl_radj": 0.081,
        "pl_bmasse": 0.77,
        "pl_bmassj": 0.0024,
        "pl_eqt": 251.0,
        "pl_dens": 5.6,
        "st_spectype": "M8V",
    },
]


@patch("app.api.exoplanets.requests.get")
def test_get_exoplanets_success(mock_get):
    mock_get.return_value = _mock_response(SAMPLE_EXOPLANETS)

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_exoplanets()

    assert result["ok"] is True
    assert result["error"] is None
    assert len(result["data"]) == 2
    assert result["data"][0]["pl_name"] == "Kepler-22 b"


@patch("app.api.exoplanets.requests.get")
def test_get_exoplanets_uses_top_not_limit(mock_get):
    """The Exoplanet Archive's Oracle/ADQL backend requires ``select top N``
    rather than ``LIMIT N``.  Verify the outgoing query shape."""
    mock_get.return_value = _mock_response(SAMPLE_EXOPLANETS)

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        get_exoplanets(limit=50)

    query = mock_get.call_args[1]["params"]["query"]
    assert "select top 50" in query.lower(), f"Expected 'select top 50', got: {query}"
    assert "limit" not in query.lower().split("from")[1], (
        f"'limit' must not appear after FROM: {query}"
    )


@patch("app.api.exoplanets.requests.get")
def test_get_exoplanets_search_keeps_default_flag(mock_get):
    """When searching, ``default_flag = 1`` must stay in the WHERE clause to
    avoid duplicate rows per planet."""
    mock_get.return_value = _mock_response([SAMPLE_EXOPLANETS[1]])

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_exoplanets(search="TRAPPIST")

    assert result["ok"] is True
    query = mock_get.call_args[1]["params"]["query"]
    assert "default_flag" in query, f"default_flag missing from search query: {query}"
    assert "TRAPPIST" in query


@patch("app.api.exoplanets.requests.get")
def test_get_exoplanets_search(mock_get):
    mock_get.return_value = _mock_response([SAMPLE_EXOPLANETS[1]])

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_exoplanets(search="TRAPPIST")

    assert result["ok"] is True
    assert len(result["data"]) == 1
    assert result["data"][0]["hostname"] == "TRAPPIST-1"
    # Verify search term was passed in query
    call_params = mock_get.call_args[1]["params"]
    assert "TRAPPIST" in call_params["query"]


@patch("app.api.exoplanets.requests.get")
def test_get_exoplanets_timeout(mock_get):
    mock_get.side_effect = Timeout("Connection timed out")

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_exoplanets()

    assert result["ok"] is False
    assert "timed out" in result["error"]


@patch("app.api.exoplanets.requests.get")
def test_get_exoplanets_rate_limit(mock_get):
    mock_get.return_value = _mock_response([], status_code=429)

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_exoplanets()

    assert result["ok"] is False
    assert "rate limit" in result["error"].lower()


@patch("app.api.exoplanets.requests.get")
def test_get_exoplanets_generic_error(mock_get):
    mock_get.side_effect = Exception("Connection refused")

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_exoplanets()

    assert result["ok"] is False
    assert "Unexpected error" in result["error"]


@patch("app.api.exoplanets.requests.get")
def test_get_exoplanets_unexpected_format(mock_get):
    mock_get.return_value = _mock_response({"error": "bad request"})

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_exoplanets()

    assert result["ok"] is False
    assert "Unexpected response format" in result["error"]


# ---------------------------------------------------------------------------
# Discovery-method filter
# ---------------------------------------------------------------------------

@patch("app.api.exoplanets.requests.get")
def test_get_exoplanets_discovery_filter_in_query(mock_get):
    """A known method must reach the ADQL WHERE clause."""
    mock_get.return_value = _mock_response([SAMPLE_EXOPLANETS[0]])

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_exoplanets(discovery="Radial Velocity")

    assert result["ok"] is True
    query = mock_get.call_args[1]["params"]["query"]
    assert "discoverymethod = 'Radial Velocity'" in query, query
    # and default_flag must survive so rows are not duplicated
    assert "default_flag = 1" in query, query


@patch("app.api.exoplanets.requests.get")
def test_get_exoplanets_search_and_discovery_combine(mock_get):
    """Both filters must be ANDed, not either/or."""
    mock_get.return_value = _mock_response([SAMPLE_EXOPLANETS[1]])

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        get_exoplanets(search="TRAPPIST", discovery="Transit")

    query = mock_get.call_args[1]["params"]["query"].lower()
    assert query.count(" where ") == 1, "must build a single WHERE clause"
    assert "default_flag = 1" in query
    assert "discoverymethod = 'transit'" in query
    assert "trappist" in query


@patch("app.api.exoplanets.requests.get")
def test_get_exoplanets_unknown_discovery_is_ignored(mock_get):
    """Anything outside the whitelist (e.g. an injection attempt) must not be
    interpolated into SQL — the filter is simply dropped."""
    mock_get.return_value = _mock_response(SAMPLE_EXOPLANETS)

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        get_exoplanets(discovery="Transit' OR '1'='1")

    query = mock_get.call_args[1]["params"]["query"]
    # discoverymethod is a SELECT column, not a WHERE condition. The filter must
    # never be interpolated, so no injection clause may survive.
    assert "discoverymethod = 'Transit' OR '1'='1'" not in query, query
    assert "OR" not in query


# ---------------------------------------------------------------------------
# get_exoplanet() — single-planet lookup
# ---------------------------------------------------------------------------

from app.api.exoplanets import get_exoplanet


@patch("app.api.exoplanets.requests.get")
def test_get_exoplanet_success(mock_get):
    """A single planet row must be returned, not wrapped in a list."""
    mock_get.return_value = _mock_response([SAMPLE_EXOPLANETS[0]])

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_exoplanet("Kepler-22 b")

    assert result["ok"] is True
    assert result["error"] is None
    assert result["data"]["pl_name"] == "Kepler-22 b"


@patch("app.api.exoplanets.requests.get")
def test_get_exoplanet_not_found_returns_none(mock_get):
    """An empty list means the planet doesn't exist; data must be None."""
    mock_get.return_value = _mock_response([])

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_exoplanet("Nonexistent-99 z")

    assert result["ok"] is True
    assert result["data"] is None


@patch("app.api.exoplanets.requests.get")
def test_get_exoplanet_timeout(mock_get):
    mock_get.side_effect = Timeout("Connection timed out")

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_exoplanet("Kepler-22 b")

    assert result["ok"] is False
    assert "timed out" in result["error"]


@patch("app.api.exoplanets.requests.get")
def test_get_exoplanet_rate_limit(mock_get):
    mock_get.return_value = _mock_response([], status_code=429)

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_exoplanet("Kepler-22 b")

    assert result["ok"] is False
    assert "rate limit" in result["error"].lower()


@patch("app.api.exoplanets.requests.get")
def test_get_exoplanet_sql_injection_guard(mock_get):
    """Single-quote escaping must survive the exact-name lookup path."""
    mock_get.return_value = _mock_response([])

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        get_exoplanet("Bob' OR '1'='1")

    query = mock_get.call_args[1]["params"]["query"]
    # The escaped quote must appear, and no bare OR clause may survive.
    assert "''" in query
    assert "OR '1'='1'" not in query
    assert "default_flag = 1" in query
