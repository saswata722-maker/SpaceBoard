import logging
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import ConnectionError, HTTPError, Timeout

from app.api.apod import SECONDARY_PROVIDER, get_apod


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


FALLBACK_IMAGE = {
    "url": "https://images-api.nasa.gov/image/PIA00001~orig.jpg",
    "media_type": "image",
    "title": "Fallback Nebula",
    "date": "2024-03-01",
    "copyright": "NASA/JPL-Caltech",
    "source": "NASA Image and Video Library",
    "nasa_id": "PIA00001",
}


def _fallback_ok(data=None):
    return {
        "ok": True,
        "data": dict(FALLBACK_IMAGE) if data is None else data,
        "error": None,
    }


def _fallback_fail(message="The NASA Image and Video Library returned no usable image."):
    return {"ok": False, "data": None, "error": message}


def _arm_primary_failure(mock_get, trigger):
    """Make the primary endpoint fail in the shape named by *trigger*."""
    if trigger == "none":
        mock_get.return_value = _mock_response(SAMPLE_APOD)
    elif trigger == "connection_error":
        mock_get.side_effect = ConnectionError("Connection refused")
    elif trigger == "timeout":
        mock_get.side_effect = Timeout("Connection timed out")
    elif trigger == "http_400":
        mock_get.return_value = _mock_response({}, status_code=400)
    elif trigger == "http_429":
        mock_get.return_value = _mock_response({}, status_code=429)
    elif trigger == "http_500_today_and_yesterday":
        mock_get.side_effect = [
            _mock_response({}, status_code=500),
            _mock_response({}, status_code=500),
        ]
    elif trigger == "empty_payload":
        mock_get.return_value = _mock_response({})
    elif trigger == "null_payload":
        mock_get.return_value = _mock_response(None)
    elif trigger == "empty_url_payload":
        mock_get.return_value = _mock_response(
            {"url": "", "media_type": "image", "title": "Record without a URL"}
        )
    else:
        raise AssertionError(f"unknown trigger: {trigger}")


@patch("app.api.apod.get_fallback_image")
@patch("app.api.apod.requests.get")
def test_get_apod_success(mock_get, mock_fallback):
    mock_get.return_value = _mock_response(SAMPLE_APOD)
    mock_fallback.return_value = _fallback_ok()

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
    mock_fallback.assert_not_called()


@patch("app.api.apod.get_fallback_image")
@patch("app.api.apod.requests.get")
def test_get_apod_always_sends_date(mock_get, mock_fallback):
    """Even when no date is passed, a ``date`` parameter must be sent to NASA
    (omitting it triggers HTTP 500 on the real endpoint)."""
    mock_get.return_value = _mock_response(SAMPLE_APOD)
    mock_fallback.return_value = _fallback_ok()

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        get_apod()  # no date argument

    call_params = mock_get.call_args[1]["params"]
    assert "date" in call_params, "date param must always be present"
    # Should be a YYYY-MM-DD string
    assert len(call_params["date"]) == 10
    mock_fallback.assert_not_called()


@patch("app.api.apod.get_fallback_image")
@patch("app.api.apod.requests.get")
def test_get_apod_with_date(mock_get, mock_fallback):
    mock_get.return_value = _mock_response(SAMPLE_APOD)
    mock_fallback.return_value = _fallback_ok()

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_apod(date="2024-01-15")

    assert result["ok"] is True
    # Verify the date param was passed through
    call_params = mock_get.call_args[1]["params"]
    assert call_params["date"] == "2024-01-15"
    mock_fallback.assert_not_called()


@patch("app.api.apod.get_fallback_image")
@patch("app.api.apod.requests.get")
def test_get_apod_fallback_on_500(mock_get, mock_fallback):
    """When today's APOD returns 500 (not published yet) and no explicit date
    was requested, the code should retry with yesterday's date."""
    fail = _mock_response({}, status_code=500)
    # Don't raise on the first call — the fallback logic checks status_code
    fail.raise_for_status = MagicMock()
    ok = _mock_response(SAMPLE_APOD)

    mock_get.side_effect = [fail, ok]
    mock_fallback.return_value = _fallback_ok()

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
    mock_fallback.assert_not_called()


@patch("app.api.apod.get_fallback_image")
@patch("app.api.apod.requests.get")
def test_get_apod_timeout(mock_get, mock_fallback):
    mock_get.side_effect = Timeout("Connection timed out")
    mock_fallback.return_value = _fallback_fail()

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_apod()

    assert result["ok"] is False
    assert result["data"] is None
    assert "timed out" in result["error"]


@patch("app.api.apod.get_fallback_image")
@patch("app.api.apod.requests.get")
def test_get_apod_rate_limit(mock_get, mock_fallback):
    mock_get.return_value = _mock_response({}, status_code=429)
    mock_fallback.return_value = _fallback_fail()

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_apod()

    assert result["ok"] is False
    assert "rate limit" in result["error"].lower()


@patch("app.api.apod.get_fallback_image")
@patch("app.api.apod.requests.get")
def test_get_apod_generic_error(mock_get, mock_fallback):
    mock_get.side_effect = Exception("Connection refused")
    mock_fallback.return_value = _fallback_fail()

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_apod()

    assert result["ok"] is False
    assert "Unexpected error" in result["error"]


@pytest.mark.parametrize(
    "trigger",
    [
        "connection_error",
        "timeout",
        "http_400",
        "http_429",
        "http_500_today_and_yesterday",
        "empty_payload",
        "null_payload",
        "empty_url_payload",
    ],
)
@patch("app.api.apod.get_fallback_image")
@patch("app.api.apod.requests.get")
def test_every_trigger_condition_fails_over(mock_get, mock_fallback, trigger):
    """IR-04 criterion 1: transport errors, timeouts, HTTP 4xx/5xx/429 and
    payloads that fail structural validation — including empty and null
    results — all fail over, and the secondary's own attribution comes back.
    """
    _arm_primary_failure(mock_get, trigger)
    mock_fallback.return_value = _fallback_ok()

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_apod()

    assert mock_get.call_count >= 1
    assert mock_fallback.call_count == 1
    assert result["ok"] is True
    assert result["error"] is None
    assert result["data"]["source"] == "NASA Image and Video Library"
    assert result["data"]["title"] == "Fallback Nebula"
    assert result["data"]["copyright"] == "NASA/JPL-Caltech"
    assert result["data"]["media_type"] == "image"
    assert result["data"]["nasa_id"] == "PIA00001"


@pytest.mark.parametrize(
    "fallback_result",
    [
        _fallback_fail(),
        {"ok": True, "data": None, "error": None},
    ],
    ids=["provider-failure", "empty-search"],
)
@patch("app.api.apod.get_fallback_image")
@patch("app.api.apod.requests.get")
def test_both_providers_down_keeps_data_unavailable(
        mock_get, mock_fallback, fallback_result):
    """IR-04 criterion 8: when both providers fail, the primary failure
    message is what the page shows, so fallback introduces no new failure
    mode."""
    mock_get.side_effect = Timeout("Connection timed out")
    mock_fallback.return_value = fallback_result

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_apod()

    assert result["ok"] is False
    assert result["data"] is None
    assert "timed out" in result["error"]


@patch("app.api.apod.get_fallback_image")
@patch("app.api.apod.requests.get")
def test_transient_outage_fails_over_then_primary_recovery_wins(
        mock_get, mock_fallback):
    """IR-04 criteria 5 and 6: a primary failure is never cached (the next
    request retries the primary), and secondary responses are cached under
    their own keys, so a fallback success cannot mask a primary recovery.
    """
    mock_get.side_effect = [ConnectionError("refused"), _mock_response(SAMPLE_APOD)]
    mock_fallback.return_value = _fallback_ok()

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        first = get_apod()
        second = get_apod()

    assert first["data"]["source"] == "NASA Image and Video Library"
    assert second["data"] == SAMPLE_APOD
    assert "source" not in second["data"]
    assert mock_fallback.call_count == 1
    assert mock_get.call_count == 2


@patch("app.api.apod.get_fallback_image")
@patch("app.api.apod.requests.get")
def test_failover_logs_trigger_and_provider(mock_get, mock_fallback, caplog):
    """IR-04 criterion 7: the failover is visible in logs at warning level
    with the triggering condition and the provider used."""
    mock_get.side_effect = Timeout("Connection timed out")
    mock_fallback.return_value = _fallback_ok()

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        with caplog.at_level(logging.WARNING):
            result = get_apod()

    assert result["ok"] is True
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("APOD failover" in r.getMessage() for r in warnings)
    assert any("timed out" in r.getMessage() for r in warnings)
    assert any(SECONDARY_PROVIDER in r.getMessage() for r in warnings)


@pytest.mark.parametrize(
    "trigger,fallback_result",
    [
        ("none", _fallback_ok()),
        ("connection_error", _fallback_ok()),
        ("timeout", _fallback_ok()),
        ("null_payload", _fallback_fail()),
        ("http_429", {"ok": True, "data": None, "error": None}),
    ],
)
@patch("app.api.apod.get_fallback_image")
@patch("app.api.apod.requests.get")
def test_result_envelope_keys_are_preserved(
        mock_get, mock_fallback, trigger, fallback_result):
    """IR-04 criterion 9: whatever happens, the envelope keeps exactly
    ok/data/error so no route or template signature changes."""
    _arm_primary_failure(mock_get, trigger)
    mock_fallback.return_value = fallback_result

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_apod()

    assert set(result) == {"ok", "data", "error"}
    assert isinstance(result["ok"], bool)
    assert result["data"] is None or isinstance(result["data"], dict)
    assert result["error"] is None or isinstance(result["error"], str)
