from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import HTTPError, Timeout

from app.api.apod import get_apod


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


SAMPLE_APOD = {
    "date": "2024-01-15",
    "explanation": "A beautiful nebula captured by a telescope.",
    "hdurl": "https://apod.nasa.gov/apod/image/test_hd.jpg",
    "media_type": "image",
    "service_version": "v1",
    "title": "Test Nebula",
    "url": "https://apod.nasa.gov/apod/image/test.jpg",
    "copyright": "Jane Astronomer",
}


@patch("app.api.apod.requests.get")
def test_get_apod_success(mock_get):
    mock_get.return_value = _mock_response(SAMPLE_APOD)

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_apod()

    assert result["ok"] is True
    assert result["error"] is None
    assert result["data"]["title"] == "Test Nebula"
    assert result["data"]["media_type"] == "image"
    assert result["data"]["date"] == "2024-01-15"


@patch("app.api.apod.requests.get")
def test_get_apod_with_date(mock_get):
    mock_get.return_value = _mock_response(SAMPLE_APOD)

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_apod(date="2024-01-15")

    assert result["ok"] is True
    # Verify the date param was passed through
    call_params = mock_get.call_args[1]["params"]
    assert call_params["date"] == "2024-01-15"


@patch("app.api.apod.requests.get")
def test_get_apod_timeout(mock_get):
    mock_get.side_effect = Timeout("Connection timed out")

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_apod()

    assert result["ok"] is False
    assert result["data"] is None
    assert "timed out" in result["error"]


@patch("app.api.apod.requests.get")
def test_get_apod_rate_limit(mock_get):
    mock_get.return_value = _mock_response({}, status_code=429)

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_apod()

    assert result["ok"] is False
    assert "rate limit" in result["error"].lower()


@patch("app.api.apod.requests.get")
def test_get_apod_generic_error(mock_get):
    mock_get.side_effect = Exception("Connection refused")

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_apod()

    assert result["ok"] is False
    assert "Unexpected error" in result["error"]
