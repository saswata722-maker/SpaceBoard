import re
from unittest.mock import call, patch

import pytest


@pytest.fixture
def client():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


FACT_SAMPLE = {
    "headline": "Sputnik 1",
    "body": "1957 — The Soviet Union launches Sputnik 1, the first artificial satellite.",
    "source_label": "Wikipedia",
    "source_url": "https://en.wikipedia.org/wiki/Sputnik_1",
}

FACT_SAMPLE_ALT = {
    "headline": "Humans in space right now",
    "body": "12 people are currently in orbit: 10 aboard the ISS, 2 aboard Tiangong.",
    "source_label": "Open Notify",
    "source_url": "http://open-notify.org/",
}

APOD_SAMPLE = {
    "date": "2024-01-15",
    "explanation": "A beautiful nebula.",
    "media_type": "image",
    "title": "Test Nebula",
    "url": "https://example.com/image.jpg",
}


def _apod_ok(data=None):
    return {
        "ok": True,
        "data": dict(APOD_SAMPLE) if data is None else data,
        "error": None,
    }


def _fact_ok(data=None):
    return {
        "ok": True,
        "data": dict(FACT_SAMPLE) if data is None else data,
        "error": None,
    }


@patch("app.routes.home.get_daily_fact")
@patch("app.routes.home.get_apod")
def test_home_route_success(mock_get_apod, mock_get_fact, client):
    mock_get_apod.return_value = _apod_ok()
    mock_get_fact.return_value = _fact_ok()
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode()
    # IR-03: the copy comes from the live fact source, with its attribution.
    assert "Sputnik 1" in html
    assert "first artificial satellite" in html
    assert 'href="https://en.wikipedia.org/wiki/Sputnik_1"' in html
    # The media block stays data-driven on APOD.
    assert "Test Nebula" in html
    assert "2024-01-15" in html


@patch("app.routes.home.get_daily_fact")
@patch("app.routes.home.get_apod")
def test_home_route_has_no_date_picker(mock_get_apod, mock_get_fact, client):
    """The picker is gone: / renders no date input and the route forwards no
    date to the API, so a date parameter cannot exist on the page at all."""
    mock_get_apod.return_value = _apod_ok()
    mock_get_fact.return_value = _fact_ok()

    response = client.get("/")
    assert response.status_code == 200
    assert b'name="date"' not in response.data
    assert b'type="date"' not in response.data
    assert b"apod_date" not in response.data
    mock_get_apod.assert_called_once_with()


@patch("app.routes.home.get_daily_fact")
@patch("app.routes.home.get_apod")
def test_home_copy_changes_with_the_source(mock_get_apod, mock_get_fact, client):
    """IR-03 criterion 1: the copy follows the source, so a different day (or a
    different source answering) renders different copy — never a rewrite."""
    mock_get_apod.return_value = _apod_ok()

    mock_get_fact.return_value = _fact_ok()
    first = client.get("/").data.decode()
    mock_get_fact.return_value = _fact_ok(dict(FACT_SAMPLE_ALT))
    second = client.get("/").data.decode()

    assert "Sputnik 1" in first
    assert "Sputnik 1" not in second
    assert "Humans in space right now" in second
    assert "10 aboard the ISS" in second
    assert 'href="http://open-notify.org/"' in second


@patch("app.routes.home.get_daily_fact")
@patch("app.routes.home.get_apod")
def test_home_copy_is_omitted_when_no_source_answers(mock_get_apod, mock_get_fact, client):
    """IR-03 criterion 2: no source answering means no copy section — not a
    built-in substitute — while the media block still renders."""
    mock_get_apod.return_value = _apod_ok()
    mock_get_fact.return_value = {"ok": True, "data": None, "error": None}

    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode()

    assert "Sputnik 1" not in html
    assert "NASA Science" not in html
    assert "No fact available" not in html
    assert "Test Nebula" in html


@patch("app.routes.home.get_daily_fact")
@patch("app.routes.home.get_apod")
def test_home_fact_is_never_the_apod_record(mock_get_apod, mock_get_fact, client):
    """IR-03 criterion 3: the copy is never presented as the day's APOD record."""
    mock_get_apod.return_value = _apod_ok()
    mock_get_fact.return_value = _fact_ok()

    html = client.get("/").data.decode()

    assert "A beautiful nebula" not in html
    assert "Test Nebula" in html  # still the media caption


@pytest.mark.parametrize(
    "api_result,expect_error_card",
    [
        pytest.param(_apod_ok(), False, id="apod-success"),
        pytest.param(
            {"ok": False, "data": None,
             "error": "NASA APOD API returned an error (HTTP 500)."},
            True,
            id="apod-http-failure",
        ),
        pytest.param(
            {"ok": False, "data": None,
             "error": "The request to NASA's APOD API timed out. Please try again."},
            True,
            id="apod-timeout",
        ),
        pytest.param(
            {"ok": False, "data": None,
             "error": "NASA API rate limit exceeded. Please wait and try again."},
            True,
            id="apod-rate-limit",
        ),
    ],
)
@patch("app.routes.home.get_daily_fact")
@patch("app.routes.home.get_apod")
def test_home_fact_renders_in_every_apod_state(
        mock_get_apod, mock_get_fact, client, api_result, expect_error_card):
    """IR-03 criterion 5: the fact section is independent of APOD's state — the
    media block and its failure card are untouched by the copy feature."""
    mock_get_apod.return_value = api_result
    mock_get_fact.return_value = _fact_ok()

    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode()

    assert "first artificial satellite" in html
    assert ("Data Unavailable" in html) is expect_error_card


@patch("app.routes.home.get_daily_fact")
@patch("app.routes.home.get_apod")
def test_home_route_api_error(mock_get_apod, mock_get_fact, client):
    mock_get_apod.return_value = {
        "ok": False,
        "data": None,
        "error": "NASA API rate limit exceeded.",
    }
    mock_get_fact.return_value = {"ok": True, "data": None, "error": None}
    response = client.get("/")
    assert response.status_code == 200
    assert b"Data Unavailable" in response.data
    assert b"rate limit" in response.data


@patch("app.routes.home.get_daily_fact")
@patch("app.routes.home.get_apod")
def test_home_route_attributes_fallback_media_to_its_source(mock_get_apod, mock_get_fact, client):
    """IR-04 criterion 4: media served by the secondary provider carries its
    own title, credit, and source line — never attributed to APOD."""
    mock_get_apod.return_value = {
        "ok": True,
        "data": {
            "url": "https://images-api.nasa.gov/image/PIA00001~orig.jpg",
            "media_type": "image",
            "title": "Fallback Nebula",
            "date": "2024-03-01",
            "copyright": "NASA/JPL-Caltech",
            "source": "NASA Image and Video Library",
            "nasa_id": "PIA00001",
        },
        "error": None,
    }
    mock_get_fact.return_value = {"ok": True, "data": None, "error": None}
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode()
    assert "Source: NASA Image and Video Library" in html
    assert "Fallback Nebula" in html
    assert "NASA/JPL-Caltech" in html


@patch("app.routes.home.get_daily_fact")
@patch("app.routes.home.get_apod")
def test_home_route_shows_no_source_line_for_primary_media(mock_get_apod, mock_get_fact, client):
    """Primary APOD records carry no source field, so no Source line renders
    for them."""
    mock_get_apod.return_value = {"ok": True, "data": dict(APOD_SAMPLE), "error": None}
    mock_get_fact.return_value = {"ok": True, "data": None, "error": None}

    html = client.get("/").data.decode()

    assert "Source:" not in html


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


@patch("app.routes.home.get_daily_fact")
@patch("app.routes.home.get_apod")
def test_home_page_declares_an_inline_favicon(mock_get_apod, mock_get_fact, client):
    """A declared inline icon keeps the browser from requesting /favicon.ico,
    which otherwise 404s (the old blueprint route lived at
    /stars/favicon.ico because of its url_prefix, so it never helped)."""
    mock_get_apod.return_value = {
        "ok": False, "data": None, "error": "mocked outage"
    }
    mock_get_fact.return_value = {"ok": True, "data": None, "error": None}

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


# ---------------------------------------------------------------------------
# Planet detail route
# ---------------------------------------------------------------------------

PLANET_DATA = {
    "id": "terre",
    "name": "Terre",
    "nameEnglish": "Earth",
    "isPlanet": True,
    "massMassValue": 5.97,
    "massExp": 24,
    "radiusMean": 6371.0,
    "gravity": 9.81,
    "semimajorAxis": 149598023,
    "eccentricity": 0.0167,
    "inclination": 0.0,
    "orbitalPeriod": 365.25,
    "moons": [{"moon": "Lune"}],
    "discoveredBy": None,
}

BODY_IMAGE = {
    "url": "https://images-assets.nasa.gov/image/PIA00001~orig.jpg",
    "title": "Earth from Deep Space",
    "credit": "NASA/JPL-Caltech",
    "nasa_id": "PIA00001",
}


def _image_ok(data=None):
    return {"ok": True, "data": dict(BODY_IMAGE) if data is None else data, "error": None}


def _image_absent():
    return {"ok": True, "data": None, "error": None}


@patch("app.routes.planets.get_body_image")
@patch("app.routes.planets.get_body")
def test_planet_detail_route_success(mock_get_body, mock_get_image, client):
    mock_get_body.return_value = {
        "ok": True,
        "data": dict(PLANET_DATA),
        "error": None,
    }
    mock_get_image.return_value = _image_absent()
    response = client.get("/planets/terre")
    assert response.status_code == 200
    html = response.data.decode()
    assert "Earth" in html
    assert "Physical Properties" in html
    assert "Lune" in html


@patch("app.routes.planets.get_body_image")
@patch("app.routes.planets.get_body")
def test_planet_detail_renders_body_image(mock_get_body, mock_get_image, client):
    """IR-01 criterion 1: the profile shows a NASA-sourced image of the
    subject body, lazily loaded and constrained by CSS."""
    mock_get_body.return_value = {"ok": True, "data": dict(PLANET_DATA), "error": None}
    mock_get_image.return_value = _image_ok()

    response = client.get("/planets/terre")
    assert response.status_code == 200
    html = response.data.decode()

    assert 'src="https://images-assets.nasa.gov/image/PIA00001~orig.jpg"' in html
    assert 'alt="Earth"' in html
    assert 'loading="lazy"' in html
    assert 'max-h-96' in html
    assert "Earth from Deep Space" in html
    assert "Image credit: NASA/JPL-Caltech" in html
    assert "Physical Properties" in html
    mock_get_image.assert_called_once_with("Earth")


@pytest.mark.parametrize("image_result", [_image_absent(), {"ok": False, "data": None, "error": "boom"}], ids=["no-image", "provider-failure"])
@patch("app.routes.planets.get_body_image")
@patch("app.routes.planets.get_body")
def test_planet_detail_without_an_image_degrades_to_stats(
        mock_get_body, mock_get_image, client, image_result):
    """IR-01 criterion 4: no image means the existing statistics layout, with
    no broken image and no placeholder tile."""
    mock_get_body.return_value = {"ok": True, "data": dict(PLANET_DATA), "error": None}
    mock_get_image.return_value = image_result

    response = client.get("/planets/terre")
    assert response.status_code == 200
    html = response.data.decode()

    assert "images-assets.nasa.gov" not in html
    assert 'loading="lazy"' not in html
    assert "Physical Properties" in html
    assert "Lune" in html


@patch("app.routes.planets.get_body_image")
@patch("app.routes.planets.get_body")
def test_planet_detail_explains_builtin_data_when_live_api_is_down(
        mock_get_body, mock_get_image, client):
    """The OpenData API needs a key; without one the detail page still renders
    from built-in data and says so instead of bouncing the visitor back."""
    mock_get_body.return_value = {
        "ok": True,
        "data": dict(PLANET_DATA),
        "error": None,
        "note": (
            "Live solar system data is unavailable (the OpenData API now needs "
            "a free API key: Solar System OpenData API returned an error "
            "(HTTP 401)). Showing built-in planet data."
        ),
    }
    mock_get_image.return_value = _image_absent()

    response = client.get("/planets/terre")
    assert response.status_code == 200
    html = response.data.decode()

    assert "Showing built-in planet data." in html
    assert "Physical Properties" in html


@patch("app.routes.planets.get_body")
def test_planet_detail_route_not_found_redirects(mock_get_body, client):
    mock_get_body.return_value = {"ok": False, "data": None, "error": "not found"}
    response = client.get("/planets/unknown-body", follow_redirects=True)
    assert response.status_code == 200
    assert b"Back to Planets" in response.data or b"Planets" in response.data


# ---------------------------------------------------------------------------
# Exoplanet detail route
# ---------------------------------------------------------------------------

EXOPLANET_DATA = {
    "pl_name": "Kepler-22 b",
    "hostname": "Kepler-22",
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
    "sy_snum": 1,
    "sy_pnum": 1,
}


@patch("app.routes.planets.get_body_image")
@patch("app.routes.planets.get_exoplanet")
def test_exoplanet_detail_route_success(mock_get_exoplanet, mock_get_image, client):
    mock_get_exoplanet.return_value = {
        "ok": True,
        "data": dict(EXOPLANET_DATA),
        "error": None,
    }
    mock_get_image.return_value = _image_absent()
    response = client.get("/planets/exoplanet/Kepler-22%20b")
    assert response.status_code == 200
    html = response.data.decode()
    assert "Kepler-22 b" in html
    assert "Host Star" in html
    assert "Kepler-22" in html


@patch("app.routes.planets.get_body_image")
@patch("app.routes.planets.get_exoplanet")
def test_exoplanet_detail_renders_body_image(mock_get_exoplanet, mock_get_image, client):
    mock_get_exoplanet.return_value = {
        "ok": True, "data": dict(EXOPLANET_DATA), "error": None
    }
    mock_get_image.return_value = _image_ok()

    response = client.get("/planets/exoplanet/Kepler-22%20b")
    assert response.status_code == 200
    html = response.data.decode()

    assert 'src="https://images-assets.nasa.gov/image/PIA00001~orig.jpg"' in html
    assert 'alt="Kepler-22 b"' in html
    assert 'loading="lazy"' in html
    assert "Image credit: NASA/JPL-Caltech" in html
    assert "Host Star" in html


@patch("app.routes.planets.get_body_image")
@patch("app.routes.planets.get_exoplanet")
def test_exoplanet_detail_without_an_image_degrades_to_stats(
        mock_get_exoplanet, mock_get_image, client):
    mock_get_exoplanet.return_value = {
        "ok": True, "data": dict(EXOPLANET_DATA), "error": None
    }
    mock_get_image.return_value = _image_absent()

    response = client.get("/planets/exoplanet/Kepler-22%20b")
    assert response.status_code == 200
    html = response.data.decode()

    assert "images-assets.nasa.gov" not in html
    assert 'loading="lazy"' not in html
    assert "Host Star" in html
    assert "Kepler-22" in html


@patch("app.routes.planets.get_exoplanet")
def test_exoplanet_detail_route_not_found_redirects(mock_get_exoplanet, client):
    mock_get_exoplanet.return_value = {"ok": False, "data": None, "error": "not found"}
    response = client.get("/planets/exoplanet/Nonexistent-99%20z", follow_redirects=True)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Asteroid detail route
# ---------------------------------------------------------------------------

NEO_DATA = {
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


@patch("app.routes.asteroids.get_body_image")
@patch("app.routes.asteroids.get_neo")
def test_asteroid_detail_route_success(mock_get_neo, mock_get_image, client):
    mock_get_neo.return_value = {"ok": True, "data": dict(NEO_DATA), "error": None}
    mock_get_image.return_value = _image_absent()
    response = client.get("/asteroids/12345")
    assert response.status_code == 200
    html = response.data.decode()
    assert "(2024 AB)" in html
    assert "Close Approaches" in html
    assert "2024-01-15" in html
    assert "Earth" in html


@patch("app.routes.asteroids.get_body_image")
@patch("app.routes.asteroids.get_neo")
def test_asteroid_detail_renders_body_image(mock_get_neo, mock_get_image, client):
    mock_get_neo.return_value = {"ok": True, "data": dict(NEO_DATA), "error": None}
    mock_get_image.return_value = _image_ok()

    response = client.get("/asteroids/12345")
    assert response.status_code == 200
    html = response.data.decode()

    assert 'src="https://images-assets.nasa.gov/image/PIA00001~orig.jpg"' in html
    assert 'alt="(2024 AB)"' in html
    assert 'loading="lazy"' in html
    assert "Image credit: NASA/JPL-Caltech" in html
    assert "Close Approaches" in html


@patch("app.routes.asteroids.get_body_image")
@patch("app.routes.asteroids.get_neo")
def test_asteroid_detail_without_an_image_degrades_to_stats(mock_get_neo, mock_get_image, client):
    mock_get_neo.return_value = {"ok": True, "data": dict(NEO_DATA), "error": None}
    mock_get_image.return_value = _image_absent()

    response = client.get("/asteroids/12345")
    assert response.status_code == 200
    html = response.data.decode()

    assert "images-assets.nasa.gov" not in html
    assert 'loading="lazy"' not in html
    assert "Close Approaches" in html


@patch("app.routes.asteroids.get_neo")
def test_asteroid_detail_route_not_found_redirects(mock_get_neo, client):
    mock_get_neo.return_value = {"ok": False, "data": None, "error": "not found"}
    response = client.get("/asteroids/99999999", follow_redirects=True)
    assert response.status_code == 200
