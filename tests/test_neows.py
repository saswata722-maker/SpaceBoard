from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import HTTPError, Timeout

from app.api.neows import _flatten_neos, get_neo_feed


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


SAMPLE_NEO_SAFE = {
    "id": "12345",
    "name": "(2024 AB)",
    "nasa_jpl_url": "https://ssd.jpl.nasa.gov/sbdb.cgi?sstr=12345",
    "absolute_magnitude_h": 22.1,
    "estimated_diameter": {
        "kilometers": {
            "estimated_diameter_min": 0.1,
            "estimated_diameter_max": 0.3,
        }
    },
    "is_potentially_hazardous_asteroid": False,
    "close_approach_data": [
        {
            "close_approach_date": "2024-01-15",
            "relative_velocity": {"kilometers_per_hour": "50000"},
            "miss_distance": {"kilometers": "3000000"},
            "orbiting_body": "Earth",
        }
    ],
}

SAMPLE_NEO_HAZARDOUS = {
    "id": "67890",
    "name": "(2024 CD)",
    "nasa_jpl_url": "https://ssd.jpl.nasa.gov/sbdb.cgi?sstr=67890",
    "absolute_magnitude_h": 19.5,
    "estimated_diameter": {
        "kilometers": {
            "estimated_diameter_min": 0.5,
            "estimated_diameter_max": 1.2,
        }
    },
    "is_potentially_hazardous_asteroid": True,
    "close_approach_data": [
        {
            "close_approach_date": "2024-01-16",
            "relative_velocity": {"kilometers_per_hour": "72000"},
            "miss_distance": {"kilometers": "1500000"},
            "orbiting_body": "Earth",
        }
    ],
}

SAMPLE_FEED = {
    "links": {"next": "", "prev": "", "self": ""},
    "element_count": 2,
    "near_earth_objects": {
        "2024-01-15": [SAMPLE_NEO_SAFE],
        "2024-01-16": [SAMPLE_NEO_HAZARDOUS],
    },
}


def test_flatten_neos_sorts_by_date():
    feed = {
        "2024-01-16": [SAMPLE_NEO_HAZARDOUS],
        "2024-01-15": [SAMPLE_NEO_SAFE],
    }
    result = _flatten_neos(feed)
    assert len(result) == 2
    assert result[0]["name"] == "(2024 AB)"  # earlier date first
    assert result[1]["name"] == "(2024 CD)"


@patch("app.api.neows.requests.get")
def test_get_neo_feed_success(mock_get):
    mock_get.return_value = _mock_response(SAMPLE_FEED)

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_neo_feed("2024-01-15", "2024-01-16")

    assert result["ok"] is True
    assert result["error"] is None
    assert result["data"]["element_count"] == 2
    assert len(result["data"]["neos"]) == 2
    assert result["data"]["neos"][0]["name"] == "(2024 AB)"  # sorted by date
    assert result["data"]["start_date"] == "2024-01-15"
    assert result["data"]["end_date"] == "2024-01-16"


@patch("app.api.neows.requests.get")
def test_get_neo_feed_timeout(mock_get):
    mock_get.side_effect = Timeout("Connection timed out")

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_neo_feed("2024-01-15", "2024-01-16")

    assert result["ok"] is False
    assert result["data"] is None
    assert "timed out" in result["error"]


@patch("app.api.neows.requests.get")
def test_get_neo_feed_rate_limit(mock_get):
    mock_get.return_value = _mock_response({}, status_code=429)

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_neo_feed("2024-01-15", "2024-01-16")

    assert result["ok"] is False
    assert "rate limit" in result["error"].lower()


@patch("app.api.neows.requests.get")
def test_get_neo_feed_generic_error(mock_get):
    mock_get.side_effect = Exception("Connection refused")

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_neo_feed("2024-01-15", "2024-01-16")

    assert result["ok"] is False
    assert "Unexpected error" in result["error"]


@patch("app.api.neows.requests.get")
def test_get_neo_feed_empty_response(mock_get):
    empty_feed = {
        "links": {"next": "", "prev": "", "self": ""},
        "element_count": 0,
        "near_earth_objects": {},
    }
    mock_get.return_value = _mock_response(empty_feed)

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_neo_feed("2024-01-15", "2024-01-16")

    assert result["ok"] is True
    assert result["data"]["neos"] == []
    assert result["data"]["element_count"] == 0


# ---------------------------------------------------------------------------
# get_neo() — single-NEO lookup
# ---------------------------------------------------------------------------

from app.api.neows import get_neo


SAMPLE_NEO_DETAIL = {
    "id": "12345",
    "name": "(2024 AB)",
    "nasa_jpl_url": "https://ssd.jpl.nasa.gov/sbdb.cgi?sstr=12345",
    "absolute_magnitude_h": 22.1,
    "estimated_diameter": {
        "kilometers": {
            "estimated_diameter_min": 0.1,
            "estimated_diameter_max": 0.3,
        }
    },
    "is_potentially_hazardous_asteroid": False,
    "close_approach_data": [
        {
            "close_approach_date": "2024-01-15",
            "relative_velocity": {"kilometers_per_hour": "50000"},
            "miss_distance": {"kilometers": "3000000"},
            "orbiting_body": "Earth",
        }
    ],
}


@patch("app.api.neows.requests.get")
def test_get_neo_success(mock_get):
    """A single NEO lookup must return the full record."""
    mock_get.return_value = _mock_response(SAMPLE_NEO_DETAIL)

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_neo("12345")

    assert result["ok"] is True
    assert result["error"] is None
    assert result["data"]["id"] == "12345"
    assert result["data"]["name"] == "(2024 AB)"
    assert result["data"]["close_approach_data"][0]["orbiting_body"] == "Earth"


@patch("app.api.neows.requests.get")
def test_get_neo_uses_lookup_url_not_feed(mock_get):
    """The detail lookup must hit the /neo/{id} endpoint, not the feed."""
    mock_get.return_value = _mock_response(SAMPLE_NEO_DETAIL)

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        get_neo("12345")

    url = mock_get.call_args[0][0]
    assert "/neo/12345" in url, f"expected lookup URL, got {url}"
    assert "/feed" not in url


@patch("app.api.neows.requests.get")
def test_get_neo_timeout(mock_get):
    mock_get.side_effect = Timeout("Connection timed out")

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_neo("12345")

    assert result["ok"] is False
    assert "timed out" in result["error"]


@patch("app.api.neows.requests.get")
def test_get_neo_rate_limit(mock_get):
    mock_get.return_value = _mock_response({}, status_code=429)

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_neo("12345")

    assert result["ok"] is False
    assert "rate limit" in result["error"].lower()


@patch("app.api.neows.requests.get")
def test_get_neo_404(mock_get):
    mock_get.return_value = _mock_response({}, status_code=404)

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_neo("99999999")

    assert result["ok"] is False
    assert "404" in result["error"]
