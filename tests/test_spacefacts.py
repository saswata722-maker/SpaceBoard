import json
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import ConnectionError, HTTPError, Timeout

from app.api.spacefacts import get_daily_fact

ONTHISDAY_URL = "https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/events"


def _app():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app


def _mock_response(payload, status_code=200):
    mock = MagicMock()
    mock.json.return_value = payload
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    return mock


def _onthisday(events):
    return {"events": events}


def _event(year, text, title=None, url=None):
    event = {
        "year": year,
        "text": text,
        "pages": [
            {
                "title": title or "Some page",
                "normalizedtitle": title or "Some page",
                "content_urls": {"desktop": {"page": url}} if url else {},
            }
        ],
    }
    return event


SPUTNIK_EVENT = _event(
    1957,
    "The Soviet Union launches <a href='Sputnik_1'>Sputnik 1</a>, the first "
    "artificial satellite.",
    title="Sputnik 1",
    url="https://en.wikipedia.org/wiki/Sputnik_1",
)

PEOPLE = {
    "number": 12,
    "people": [
        {"craft": "ISS", "name": "Oleg Kononenko"},
        {"craft": "ISS", "name": "Tracy Caldwell Dyson"},
        {"craft": "Tiangong", "name": "Ye Guangfu"},
    ],
}

FIREBALL = {
    "signature": {"source": "NASA/JPL Fireball Data API"},
    "count": "1",
    "fields": ["date", "energy", "impact-e", "lat", "lat-dir", "lon", "lon-dir", "alt", "vel"],
    "data": [["2026-10-04 03:14:45", "5.4", "0.18", "41.8", "S", "173.1", "W", "26.9", "13.8"]],
}


def _get_daily_fact_with_cleared_cache():
    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        return get_daily_fact()


# ---------------------------------------------------------------------------
# Primary source: Wikipedia's On This Day feed
# ---------------------------------------------------------------------------

@patch("app.api.spacefacts.requests.get")
def test_fact_comes_from_onthisday_for_todays_date(mock_get):
    mock_get.return_value = _mock_response(_onthisday([SPUTNIK_EVENT]))

    result = _get_daily_fact_with_cleared_cache()

    assert result["ok"] is True
    args, kwargs = mock_get.call_args
    assert args[0].startswith(ONTHISDAY_URL)
    assert result["data"]["headline"] == "Sputnik 1"
    assert "first artificial satellite" in result["data"]["body"]
    assert result["data"]["source_label"] == "Wikipedia"
    assert result["data"]["source_url"] == "https://en.wikipedia.org/wiki/Sputnik_1"


@patch("app.api.spacefacts.requests.get")
def test_fact_strips_inline_html_and_prefixes_the_year(mock_get):
    mock_get.return_value = _mock_response(_onthisday([SPUTNIK_EVENT]))

    result = _get_daily_fact_with_cleared_cache()

    body = result["data"]["body"]
    assert "<a href" not in body
    assert "Sputnik 1, the first artificial satellite" in body
    assert body.startswith("1957 — ")


@patch("app.api.spacefacts.requests.get")
def test_non_space_events_are_skipped(mock_get):
    mock_get.return_value = _mock_response(
        _onthisday([
            _event(1066, "The Norman conquest of England begins at Hastings."),
            _event(1492, "Christopher Columbus reaches the Americas."),
            _event(1957, "The Soviet Union launches Sputnik 1, the first satellite."),
        ])
    )

    result = _get_daily_fact_with_cleared_cache()

    assert result["data"]["body"].startswith("1957 — ")


@patch("app.api.spacefacts.requests.get")
def test_dated_url_uses_month_and_day(mock_get):
    mock_get.return_value = _mock_response(_onthisday([SPUTNIK_EVENT]))

    _get_daily_fact_with_cleared_cache()

    from datetime import date

    today = date.today()
    assert f"/{today.strftime('%m')}/{today.strftime('%d')}" in mock_get.call_args[0][0]


@patch("app.api.spacefacts.requests.get")
def test_requests_carry_a_user_agent(mock_get):
    mock_get.return_value = _mock_response(_onthisday([SPUTNIK_EVENT]))

    _get_daily_fact_with_cleared_cache()

    assert mock_get.call_args[1]["headers"]["User-Agent"]


# ---------------------------------------------------------------------------
# Fallback chain
# ---------------------------------------------------------------------------

@patch("app.api.spacefacts.requests.get")
def test_falls_back_to_people_in_space_when_no_space_event(mock_get):
    mock_get.side_effect = [
        _mock_response(_onthisday([_event(1066, "The Norman conquest begins.")])),
        _mock_response(PEOPLE),
    ]

    result = _get_daily_fact_with_cleared_cache()

    assert result["data"]["headline"] == "Humans in space right now"
    assert "12 people are currently in orbit" in result["data"]["body"]
    assert "2 aboard the ISS" in result["data"]["body"]
    assert "1 aboard the Tiangong" in result["data"]["body"]
    assert result["data"]["source_label"] == "Open Notify"


@patch("app.api.spacefacts.requests.get")
def test_falls_back_to_fireball_when_earlier_sources_fail(mock_get):
    mock_get.side_effect = [
        MagicMock(status_code=500, **{"raise_for_status.side_effect": HTTPError()}),
        MagicMock(status_code=503, **{"raise_for_status.side_effect": HTTPError()}),
        _mock_response(FIREBALL),
    ]

    result = _get_daily_fact_with_cleared_cache()

    assert result["data"]["headline"] == "Latest bright fireball"
    assert "2026-10-04" in result["data"]["body"]
    assert "5.4 kilotons" in result["data"]["body"]
    assert result["data"]["source_label"] == "NASA/JPL"


@patch("app.api.spacefacts.requests.get")
def test_fireball_body_reports_place_and_energy(mock_get):
    mock_get.return_value = _mock_response(FIREBALL)

    result = _get_daily_fact_with_cleared_cache()

    assert "41.8°S" in result["data"]["body"]
    assert "173.1°W" in result["data"]["body"]


@patch("app.api.spacefacts.requests.get")
def test_all_sources_down_yields_no_data_and_no_builtin_copy(mock_get):
    mock_get.side_effect = ConnectionError("network down")

    result = _get_daily_fact_with_cleared_cache()

    assert result["ok"] is True
    assert result["data"] is None
    assert result["error"] is None


@pytest.mark.parametrize(
    "side_effect",
    [
        Timeout("Connection timed out"),
        ConnectionError("Connection refused"),
    ],
    ids=["timeout", "connection-error"],
)
@patch("app.api.spacefacts.requests.get")
def test_transport_errors_never_raise(mock_get, side_effect):
    mock_get.side_effect = side_effect

    result = _get_daily_fact_with_cleared_cache()

    assert result["ok"] is True
    assert result["data"] is None


@patch("app.api.spacefacts.requests.get")
def test_source_returning_garbage_falls_through(mock_get):
    mock_get.side_effect = [
        _mock_response({"events": "not a list"}),
        _mock_response({"people": None}),
        _mock_response({"fields": None, "data": None}),
    ]

    result = _get_daily_fact_with_cleared_cache()

    assert result["ok"] is True
    assert result["data"] is None


@patch("app.api.spacefacts.requests.get")
def test_each_source_is_tried_in_order(mock_get):
    mock_get.side_effect = [
        _mock_response(_onthisday([SPUTNIK_EVENT])),
        _mock_response(PEOPLE),
        _mock_response(FIREBALL),
    ]

    result = _get_daily_fact_with_cleared_cache()

    assert result["data"]["source_label"] == "Wikipedia"
    assert mock_get.call_count == 1


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

@patch("app.api.spacefacts.requests.get")
def test_fact_is_memoized_per_date(mock_get):
    """Two requests on the same day hit the feed once; the next calendar day
    gets a fresh fact — which is what makes the copy change daily."""
    mock_get.return_value = _mock_response(_onthisday([SPUTNIK_EVENT]))

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        first = get_daily_fact()
        second = get_daily_fact()
        assert mock_get.call_count == 1
        assert first["data"] == second["data"]

    from datetime import date, timedelta

    yesterday = date.today() - timedelta(days=1)
    with patch("app.api.spacefacts._date") as mock_date:
        mock_date.today.return_value = yesterday
        mock_date.side_effect = lambda *a, **k: date(*a, **k)

        app = _app()
        with app.app_context():
            from app.cache import cache

            cache.clear()
            third = get_daily_fact()

    assert mock_get.call_count == 2
    assert third["data"]["headline"] == "Sputnik 1"
