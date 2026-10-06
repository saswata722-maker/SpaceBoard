import re
from unittest.mock import patch

import pytest


@pytest.fixture
def client():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@patch("app.routes.home.get_apod")
def test_home_route_success(mock_get_apod, client):
    mock_get_apod.return_value = {
        "ok": True,
        "data": {
            "date": "2024-01-15",
            "explanation": "A beautiful nebula.",
            "media_type": "image",
            "title": "Test Nebula",
            "url": "https://example.com/image.jpg",
        },
        "error": None,
    }
    response = client.get("/")
    assert response.status_code == 200
    assert b"Test Nebula" in response.data
    assert b"A beautiful nebula" in response.data


@patch("app.routes.home.get_apod")
def test_home_route_api_error(mock_get_apod, client):
    mock_get_apod.return_value = {
        "ok": False,
        "data": None,
        "error": "NASA API rate limit exceeded.",
    }
    response = client.get("/")
    assert response.status_code == 200
    assert b"Data Unavailable" in response.data
    assert b"rate limit" in response.data


@patch("app.routes.asteroids.get_neo_feed")
def test_asteroids_route_success(mock_get_neo_feed, client):
    mock_get_neo_feed.return_value = {
        "ok": True,
        "data": {
            "neos": [
                {
                    "name": "(2024 AB)",
                    "is_potentially_hazardous_asteroid": False,
                    "estimated_diameter": {
                        "kilometers": {
                            "estimated_diameter_min": 0.1,
                            "estimated_diameter_max": 0.3,
                        }
                    },
                    "close_approach_data": [
                        {
                            "close_approach_date": "2024-01-15",
                            "miss_distance": {"kilometers": "3000000"},
                            "relative_velocity": {"kilometers_per_hour": "50000"},
                        }
                    ],
                }
            ],
            "element_count": 1,
            "start_date": "2024-01-15",
            "end_date": "2024-01-22",
        },
        "error": None,
    }
    response = client.get("/asteroids/")
    assert response.status_code == 200
    assert b"(2024 AB)" in response.data
    assert b"Safe" in response.data


@patch("app.routes.asteroids.get_neo_feed")
def test_asteroids_route_hazardous_filter(mock_get_neo_feed, client):
    mock_get_neo_feed.return_value = {
        "ok": True,
        "data": {
            "neos": [
                {
                    "name": "(2024 CD)",
                    "is_potentially_hazardous_asteroid": True,
                    "estimated_diameter": {
                        "kilometers": {
                            "estimated_diameter_min": 0.5,
                            "estimated_diameter_max": 1.2,
                        }
                    },
                    "close_approach_data": [
                        {
                            "close_approach_date": "2024-01-16",
                            "miss_distance": {"kilometers": "1500000"},
                            "relative_velocity": {"kilometers_per_hour": "72000"},
                        }
                    ],
                }
            ],
            "element_count": 1,
            "start_date": "2024-01-15",
            "end_date": "2024-01-22",
        },
        "error": None,
    }
    response = client.get("/asteroids/?hazardous=on")
    assert response.status_code == 200
    assert b"Hazardous" in response.data


@patch("app.routes.asteroids.get_neo_feed")
def test_asteroids_route_api_error(mock_get_neo_feed, client):
    mock_get_neo_feed.return_value = {
        "ok": False,
        "data": None,
        "error": "Could not reach NASA API.",
    }
    response = client.get("/asteroids/")
    assert response.status_code == 200
    assert b"Data Unavailable" in response.data


@patch("app.routes.asteroids.get_neo_feed")
def test_asteroids_route_with_date_params(mock_get_neo_feed, client):
    mock_get_neo_feed.return_value = {
        "ok": True,
        "data": {
            "neos": [],
            "element_count": 0,
            "start_date": "2024-06-01",
            "end_date": "2024-06-07",
        },
        "error": None,
    }
    response = client.get(
        "/asteroids/?start_date=2024-06-01&end_date=2024-06-07"
    )
    assert response.status_code == 200


def test_404_route(client):
    response = client.get("/nonexistent-page")
    assert response.status_code == 404
    assert b"404" in response.data
    assert b"deep space" in response.data


@patch("app.routes.planets.get_planets")
@patch("app.routes.planets.get_exoplanets")
def test_planets_route_success(mock_get_exoplanets, mock_get_planets, client):
    mock_get_planets.return_value = {
        "ok": True,
        "data": [
            {
                "nameEnglish": "Earth",
                "name": "Terre",
                "massMassValue": 5.97,
                "massExp": 24,
                "radiusMean": 6371.0,
                "gravity": 9.81,
                "orbitalPeriod": 365.25,
                "moons": [{"moon": "Lune"}],
            }
        ],
        "error": None,
        "note": None,
    }
    mock_get_exoplanets.return_value = {
        "ok": True,
        "data": [{"pl_name": "Kepler-22 b", "hostname": "Kepler-22",
                   "discoverymethod": "Transit", "disc_year": 2011,
                   "pl_orbper": 289.86, "pl_rade": 2.38,
                   "pl_bmasse": 9.1, "pl_eqt": 279.0}],
        "error": None,
    }
    response = client.get("/planets/")
    assert response.status_code == 200
    assert b"Earth" in response.data
    assert b"Kepler-22 b" in response.data


@patch("app.routes.planets.get_planets")
@patch("app.routes.planets.get_exoplanets")
def test_planets_route_search(mock_get_exoplanets, mock_get_planets, client):
    mock_get_planets.return_value = {"ok": True, "data": [], "error": None, "note": None}
    mock_get_exoplanets.return_value = {
        "ok": True,
        "data": [{"pl_name": "TRAPPIST-1e", "hostname": "TRAPPIST-1",
                   "discoverymethod": "Transit", "disc_year": 2017,
                   "pl_orbper": 6.1, "pl_rade": 0.91,
                   "pl_bmasse": 0.77, "pl_eqt": 251.0}],
        "error": None,
    }
    response = client.get("/planets/?search=TRAPPIST")
    assert response.status_code == 200
    assert b"TRAPPIST-1e" in response.data


@patch("app.routes.planets.get_planets")
@patch("app.routes.planets.get_exoplanets")
def test_planets_route_api_error(mock_get_exoplanets, mock_get_planets, client):
    """The planets page never 500s: the solar section falls back to built-in
    data and shows a note, while exoplanet failures still show the old
    'Data Unavailable' block."""
    mock_get_planets.return_value = {
        "ok": True,
        "data": [],
        "error": None,
        "note": "Live solar system data is unavailable. Showing built-in planet data.",
    }
    mock_get_exoplanets.return_value = {
        "ok": False, "data": None, "error": "Archive timeout."
    }
    response = client.get("/planets/")
    assert response.status_code == 200
    assert b"built-in planet data" in response.data
    assert b"Data Unavailable" in response.data


@patch("app.routes.stars.get_apod")
def test_stars_route_success(mock_get_apod, client):
    # Simulate 8 days of APOD calls (today minus 7 days through today)
    mock_get_apod.return_value = {
        "ok": True,
        "data": {
            "date": "2024-01-15",
            "explanation": "A star field.",
            "media_type": "image",
            "title": "Test Star Image",
            "url": "https://example.com/star.jpg",
        },
        "error": None,
    }
    response = client.get("/stars/")
    assert response.status_code == 200
    assert b"Stars" in response.data


@patch("app.routes.stars.get_apod")
def test_stars_route_empty(mock_get_apod, client):
    mock_get_apod.return_value = {"ok": True, "data": None, "error": None}
    response = client.get("/stars/")
    assert response.status_code == 200
    assert b"No recent imagery" in response.data


@patch("app.routes.stars.get_apod")
def test_stars_route_uses_mocked_apod_not_real_api(mock_get_apod, client):
    """Regression guard: the view must call the module-level `get_apod` name so
    @patch takes effect. A function-local re-import bypassed the mock, which
    made these tests hit NASA's real API and pass or fail on network state."""
    mock_get_apod.return_value = {"ok": True, "data": None, "error": None}

    response = client.get("/stars/")

    assert response.status_code == 200
    # today back through 7 days = 8 gallery slots
    assert mock_get_apod.call_count == 8
    assert b"No recent imagery" in response.data


# ---------------------------------------------------------------------------
# "Where to find this planet tonight" (client-side astronomy-engine block)
# ---------------------------------------------------------------------------

TONIGHT_SCRIPT = "js/planet-tonight.js"


@patch("app.routes.planets.get_exoplanets")
@patch("app.routes.planets.get_planets")
def test_planets_route_tonight_block_markup(mock_get_planets, mock_get_exoplanets, client):
    """Every solar-system card with an English name carries the data attribute
    the script reads, and the page loads the script."""
    mock_get_planets.return_value = {
        "ok": True,
        "data": [
            {
                "nameEnglish": "Mars",
                "name": "Mars",
                "massMassValue": 6.39,
                "massExp": 23,
                "radiusMean": 3389.5,
                "gravity": 3.71,
                "orbitalPeriod": 687.0,
                "moons": [],
            }
        ],
        "error": None,
        "note": None,
    }
    mock_get_exoplanets.return_value = {"ok": True, "data": [], "error": None}

    response = client.get("/planets/")
    assert response.status_code == 200
    html = response.data
    assert b'data-planet="Mars"' in html
    assert b"planet-tonight" in html
    assert TONIGHT_SCRIPT.encode() in html


@patch("app.routes.planets.get_exoplanets")
@patch("app.routes.planets.get_planets")
def test_planets_route_tonight_block_skipped_without_english_name(
        mock_get_planets, mock_get_exoplanets, client):
    """A body without nameEnglish cannot be mapped to an engine Body, so no
    tonight block is emitted for it."""
    mock_get_planets.return_value = {
        "ok": True,
        "data": [{
            "nameEnglish": None,
            "name": "Terre",
            "massMassValue": 5.97,
            "massExp": 24,
            "radiusMean": 6371.0,
            "gravity": 9.81,
            "orbitalPeriod": 365.25,
            "moons": [],
        }],
        "error": None,
        "note": None,
    }
    mock_get_exoplanets.return_value = {"ok": True, "data": [], "error": None}

    html = client.get("/planets/").data
    assert b"data-planet" not in html


@patch("app.routes.planets.get_exoplanets")
@patch("app.routes.planets.get_planets")
def test_planets_route_engine_url_is_loadable(
        mock_get_planets, mock_get_exoplanets, client):
    """Regression guard: cdn.jsdelivr.net/npm/astronomy-engine has no dist/
    directory and version 2.1.10 was never published, so the old URL 404'd and
    the feature failed silently."""
    mock_get_planets.return_value = {"ok": True, "data": [], "error": None, "note": None}
    mock_get_exoplanets.return_value = {"ok": True, "data": [], "error": None}

    html = client.get("/planets/").data.decode()
    assert "astronomy-engine@" in html
    assert "/dist/" not in html

    match = re.search(r"astronomy-engine@(\d+\.\d+\.\d+)/([\w.]+)\.js", html)
    assert match, "engine script URL must pin a version and a real file name"
    assert match.group(2) == "astronomy.browser.min"


def test_planet_tonight_script_served_and_uses_verified_api(client):
    """The script is served, reads the card attribute, and uses the
    astronomy-engine calls that were verified against the library source
    (Equator/Horizon/Constellation/SearchRiseSet) - not the non-existent
    Epoch/Epicycle/JulianDate.fromDate calls the sky map originally used."""
    response = client.get("/static/js/planet-tonight.js")
    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert "data-planet" in body
    for call in ("Astronomy.Equator(", "Astronomy.Horizon(",
                 "Astronomy.Constellation(", "Astronomy.SearchRiseSet(",
                 "Astronomy.MakeTime("):
        assert call in body, f"expected {call} in planet-tonight.js"

    for broken in ("Astronomy.Epoch", "Astronomy.Epicycle", "JulianDate.fromDate"):
        assert broken not in body, f"{broken} does not exist in astronomy-engine"


@patch("app.routes.home.get_apod")
def test_home_page_declares_an_inline_favicon(mock_get_apod, client):
    """A declared inline icon keeps the browser from requesting /favicon.ico,
    which otherwise 404s (the old blueprint route lived at
    /stars/favicon.ico because of its url_prefix, so it never helped)."""
    mock_get_apod.return_value = {
        "ok": False, "data": None, "error": "mocked outage"
    }

    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode()
    assert 'rel="icon"' in html
    assert "data:image/svg+xml" in html


def test_root_favicon_is_served(client):
    """Browsers also probe /favicon.ico directly; it must not 404."""
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("image/svg+xml")
    assert b"<svg" in response.data


@patch("app.routes.planets.get_exoplanets")
@patch("app.routes.planets.get_planets")
def test_planets_and_sky_pages_declare_an_inline_favicon(
        mock_get_planets, mock_get_exoplanets, client):
    mock_get_planets.return_value = {"ok": True, "data": [], "error": None, "note": None}
    mock_get_exoplanets.return_value = {"ok": True, "data": [], "error": None}

    for path in ("/sky/", "/planets/"):
        html = client.get(path).data.decode()
        assert 'rel="icon"' in html, f"{path} does not declare a favicon"
        assert "data:image/svg+xml" in html, f"{path} favicon is not inline"


# ---------------------------------------------------------------------------
# APOD gallery date-range picker / paging
# ---------------------------------------------------------------------------

def _gallery_range(html):
    """Return (start, end) from the gallery's "Showing ... from ... to ..." line."""
    match = re.search(r"from (\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})", html)
    return match.groups() if match else (None, None)


@patch("app.routes.stars.get_apod")
def test_stars_default_window_fetches_eight_days(mock_get_apod, client):
    mock_get_apod.return_value = {"ok": True, "data": None, "error": None}

    response = client.get("/stars/")

    assert response.status_code == 200
    assert mock_get_apod.call_count == 8, "default window is 8 days"


@patch("app.routes.stars.get_apod")
def test_stars_honours_requested_range(mock_get_apod, client):
    """A requested window drives how many days are fetched."""
    mock_get_apod.return_value = {"ok": True, "data": None, "error": None}

    response = client.get("/stars/?start=2024-05-01&end=2024-05-10")

    assert response.status_code == 200
    assert mock_get_apod.call_count == 10
    assert _gallery_range(response.data.decode()) == ("2024-05-01", "2024-05-10")


@patch("app.routes.stars.get_apod")
def test_stars_clamps_range_to_thirty_days(mock_get_apod, client):
    """APOD has no limit, but a window wider than MAX_GALLERY_DAYS would fire
    dozens of upstream requests for one page view."""
    mock_get_apod.return_value = {"ok": True, "data": None, "error": None}

    response = client.get("/stars/?start=2024-01-01&end=2024-03-31")

    assert mock_get_apod.call_count == 30
    from datetime import date as _d
    start, end = _gallery_range(response.data.decode())
    assert start != "2024-01-01", "window start should have been clamped"
    assert (_d.fromisoformat(end) - _d.fromisoformat(start)).days + 1 == 30


@patch("app.routes.stars.get_apod")
def test_stars_ignores_future_dates(mock_get_apod, client):
    """APOD has nothing for tomorrow; the window must not run past today."""
    mock_get_apod.return_value = {"ok": True, "data": None, "error": None}

    response = client.get("/stars/?start=2099-01-01&end=2099-01-31")

    from datetime import date
    start, end = _gallery_range(response.data.decode())
    assert end == date.today().isoformat()
    assert start == date.today().isoformat()


@patch("app.routes.stars.get_apod")
def test_stars_invalid_dates_fall_back_to_default(mock_get_apod, client):
    """Garbage in the query string must not blow up the page."""
    mock_get_apod.return_value = {"ok": True, "data": None, "error": None}

    response = client.get("/stars/?start=nonsense&end=&other=1")

    assert response.status_code == 200
    assert mock_get_apod.call_count == 8
    start, end = _gallery_range(response.data.decode())
    assert start and end


@patch("app.routes.stars.get_apod")
def test_stars_paging_links_render(mock_get_apod, client):
    mock_get_apod.return_value = {"ok": True, "data": None, "error": None}

    html = client.get("/stars/").data.decode()

    assert "Newer" in html, "previous-window link missing"
    assert "Older" in html, "next-window link missing"
    # the previous link must point at an older window
    prev = re.search(r'start=(\d{4}-\d{2}-\d{2})&amp;end=(\d{4}-\d{2}-\d{2})', html)
    assert prev, "paging link has no start/end params"
    from datetime import date as _d
    assert _d.fromisoformat(prev.group(2)) < _d.fromisoformat(_gallery_range(html)[1])


# ---------------------------------------------------------------------------
# Exoplanet discovery-method dropdown
# ---------------------------------------------------------------------------

@patch("app.routes.planets.get_exoplanets")
@patch("app.routes.planets.get_planets")
def test_planets_route_renders_discovery_dropdown(
        mock_get_planets, mock_get_exoplanets, client):
    mock_get_planets.return_value = {"ok": True, "data": [], "error": None, "note": None}
    mock_get_exoplanets.return_value = {"ok": True, "data": [], "error": None}

    html = client.get("/planets/").data.decode()

    assert 'id="method"' in html, "discovery-method select missing"
    assert "All discovery methods" in html
    for method in ("Transit", "Radial Velocity", "Microlensing", "Imaging"):
        assert f"<option value=\"{method}\"" in html, f"{method} not offered"


@patch("app.routes.planets.get_exoplanets")
@patch("app.routes.planets.get_planets")
def test_planets_route_passes_method_to_api(
        mock_get_planets, mock_get_exoplanets, client):
    mock_get_planets.return_value = {"ok": True, "data": [], "error": None, "note": None}
    mock_get_exoplanets.return_value = {"ok": True, "data": [], "error": None}

    html = client.get("/planets/?method=Radial+Velocity").data.decode()

    assert mock_get_exoplanets.call_args[1].get("discovery") == "Radial Velocity"
    assert 'value="Radial Velocity" selected' in html


@patch("app.routes.planets.get_exoplanets")
@patch("app.routes.planets.get_planets")
def test_planets_route_ignores_unknown_method(
        mock_get_planets, mock_get_exoplanets, client):
    """An off-list method is dropped by the route, not passed upstream."""
    mock_get_planets.return_value = {"ok": True, "data": [], "error": None, "note": None}
    mock_get_exoplanets.return_value = {"ok": True, "data": [], "error": None}

    client.get("/planets/?method=Definitely+Not+A+Method")

    assert mock_get_exoplanets.call_args[1].get("discovery") is None
