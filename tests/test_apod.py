from unittest.mock import MagicMock, patch, call

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
def test_get_apod_always_sends_date(mock_get):
    """Even when no date is passed, a ``date`` parameter must be sent to NASA
    (omitting it triggers HTTP 500 on the real endpoint)."""
    mock_get.return_value = _mock_response(SAMPLE_APOD)

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        get_apod()  # no date argument

    call_params = mock_get.call_args[1]["params"]
    assert "date" in call_params, "date param must always be present"
    # Should be a YYYY-MM-DD string
    assert len(call_params["date"]) == 10


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
def test_get_apod_fallback_on_500(mock_get):
    """When today's APOD returns 500 (not published yet) and no explicit date
    was requested, the code should retry with yesterday's date."""
    fail = _mock_response({}, status_code=500)
    # Don't raise on the first call — the fallback logic checks status_code
    fail.raise_for_status = MagicMock()
    ok = _mock_response(SAMPLE_APOD)

    mock_get.side_effect = [fail, ok]

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_apod()  # no explicit date → should retry

    assert result["ok"] is True
    assert mock_get.call_count == 2
    # Second call should use yesterday's date
    second_params = mock_get.call_args_list[1][1]["params"]
    assert "date" in second_params


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
