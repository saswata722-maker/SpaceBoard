from unittest.mock import patch

import pytest


@pytest.fixture
def client():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# ---------------------------------------------------------------------------
# Sky map route
# ---------------------------------------------------------------------------

@patch("app.routes.sky.get_bodies")
def test_sky_map_route_success(mock_get_bodies, client):
    """The /sky/ route should render the planisphere page with the canvas."""
    mock_get_bodies.return_value = {"ok": True, "data": [], "error": None}
    response = client.get("/sky/")
    assert response.status_code == 200
    html = response.data
    assert b"sky-canvas" in html
    assert b"Sky Map" in html
    assert b"latitude" in html.lower() or b"Latitude" in html


@patch("app.routes.sky.get_bodies")
def test_sky_map_route_has_planet_api_endpoint(mock_get_bodies, client):
    """The planet-positions JSON endpoint is reachable from /sky/."""
    mock_get_bodies.return_value = {"ok": True, "data": [], "error": None}
    response = client.get("/sky/api/planet-positions")
    assert response.content_type.startswith("application/json")


# ---------------------------------------------------------------------------
# /sky/api/planet-positions
# ---------------------------------------------------------------------------

@patch("app.routes.sky.get_bodies")
def test_planet_positions_api_success(mock_get_bodies, client):
    """Successful response returns ok=True and a planets list with correct
    field names the sky map JS consumes."""
    mock_get_bodies.return_value = {
        "ok": True,
        "data": [
            {
                "id": "399",
                "nameEnglish": "Earth",
                "name": "Terre",
                "semimajorAxis": 1.0,
                "eccentricity": 0.0167,
                "inclination": 0.0,
                "meanLongitude": 100.0,
                "perihelionLongitude": 102.0,
                "orbitalPeriod": 365.25,
                "massMassValue": 5.97,
                "massExp": 24,
                "radiusMean": 6371.0,
                "isPlanet": True,
            },
            {
                "id": "499",
                "nameEnglish": "Mars",
                "name": "Mars",
                "semimajorAxis": 1.524,
                "eccentricity": 0.0934,
                "inclination": 1.85,
                "meanLongitude": 300.0,
                "perihelionLongitude": 336.0,
                "orbitalPeriod": 687.0,
                "massMassValue": 6.39,
                "massExp": 23,
                "radiusMean": 3389.5,
                "isPlanet": True,
            },
        ],
        "error": None,
    }

    response = client.get("/sky/api/planet-positions")
    assert response.status_code == 200

    data = response.get_json()
    assert data is not None
    assert data["ok"] is True
    assert "planets" in data
    assert isinstance(data["planets"], list)
    assert len(data["planets"]) == 2

    earth, mars = data["planets"]
    assert earth["id"] == "399"
    assert earth["name"] == "Earth"
    assert earth["semi_major_au"] == pytest.approx(1.0)
    assert earth["eccentricity"] == pytest.approx(0.0167)
    assert earth["inclination_deg"] == pytest.approx(0.0)
    assert earth["mean_longitude_deg"] == pytest.approx(100.0)
    assert earth["perihelion_longitude_deg"] == pytest.approx(102.0)
    assert earth["orbital_period_days"] == pytest.approx(365.25)
    assert earth["mass_kg"] == pytest.approx(5.97e24)
    assert earth["radius_km"] == pytest.approx(6371.0)

    assert mars["id"] == "499"
    assert mars["name"] == "Mars"
    assert mars["semi_major_au"] == pytest.approx(1.524)
    assert mars["eccentricity"] == pytest.approx(0.0934)
    assert mars["inclination_deg"] == pytest.approx(1.85)
    assert mars["mean_longitude_deg"] == pytest.approx(300.0)
    assert mars["perihelion_longitude_deg"] == pytest.approx(336.0)
    assert mars["orbital_period_days"] == pytest.approx(687.0)
    assert mars["mass_kg"] == pytest.approx(6.39e23)

    assert mars["radius_km"] == pytest.approx(3389.5)


@patch("app.routes.sky.get_bodies")
def test_planet_positions_api_success_name_fallback(mock_get_bodies, client):
    """When nameEnglish is missing the route falls back to a capitalized name."""
    mock_get_bodies.return_value = {
        "ok": True,
        "data": [
            {
                "id": "10",
                "name": "mercure",
                "semimajorAxis": 0.387,
                "eccentricity": 0.2056,
                "inclination": 7.0,
                "meanLongitude": 50.0,
                "perihelionLongitude": 77.0,
                "orbitalPeriod": 88.0,
                "massMassValue": 3.30,
                "massExp": 23,
                "radiusMean": 2439.7,
                "isPlanet": True,
            }
        ],
        "error": None,
    }

    response = client.get("/sky/api/planet-positions")
    assert response.status_code == 200

    data = response.get_json()
    assert data["ok"] is True
    assert len(data["planets"]) == 1
    p = data["planets"][0]
    assert p["name"] == "Mercure"


@patch("app.routes.sky.get_bodies")
def test_planet_positions_api_missing_name_skipped(mock_get_bodies, client):
    """Bodies without a name (nameEnglish or name) are excluded from the
    response."""
    mock_get_bodies.return_value = {
        "ok": True,
        "data": [
            {
                "id": "999",
                "nameEnglish": None,
                "name": None,
                "semimajorAxis": 1.0,
                "eccentricity": 0.0,
                "inclination": 0.0,
                "meanLongitude": 0.0,
                "perihelionLongitude": 0.0,
                "orbitalPeriod": 365.0,
                "massMassValue": None,
                "massExp": None,
                "radiusMean": None,
                "isPlanet": True,
            }
        ],
        "error": None,
    }

    response = client.get("/sky/api/planet-positions")
    assert response.status_code == 200

    data = response.get_json()
    assert data["ok"] is True
    assert data["planets"] == []


@patch("app.routes.sky.get_bodies")
def test_planet_positions_api_error(mock_get_bodies, client):
    """When the solar-system API fails the endpoint returns ok=False and 500."""
    mock_get_bodies.return_value = {
        "ok": False,
        "data": None,
        "error": "Upstream API timed out.",
    }

    response = client.get("/sky/api/planet-positions")
    assert response.status_code == 500

    data = response.get_json()
    assert data is not None
    assert data["ok"] is False
    assert data["error"] == "Upstream API timed out."
    assert "planets" not in data


@patch("app.routes.sky.get_bodies")
def test_planet_positions_memoized(mock_get_bodies, client):
    """The planet-positions endpoint is memoized (60 s): two identical requests
    hit the upstream API only once and return identical payloads."""
    from app.cache import cache

    cache.clear()

    first = client.get("/sky/api/planet-positions")
    assert first.status_code == 200
    second = client.get("/sky/api/planet-positions")
    assert second.status_code == 200
    assert mock_get_bodies.call_count == 1
    assert first.get_json() == second.get_json()