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
