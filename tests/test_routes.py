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


@patch("app.routes.planets.get_bodies")
@patch("app.routes.planets.get_exoplanets")
def test_planets_route_success(mock_get_exoplanets, mock_get_bodies, client):
    mock_get_bodies.return_value = {
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


@patch("app.routes.planets.get_bodies")
@patch("app.routes.planets.get_exoplanets")
def test_planets_route_search(mock_get_exoplanets, mock_get_bodies, client):
    mock_get_bodies.return_value = {"ok": True, "data": [], "error": None}
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


@patch("app.routes.planets.get_bodies")
@patch("app.routes.planets.get_exoplanets")
def test_planets_route_api_error(mock_get_exoplanets, mock_get_bodies, client):
    mock_get_bodies.return_value = {
        "ok": False, "data": None, "error": "API unreachable."
    }
    mock_get_exoplanets.return_value = {
        "ok": False, "data": None, "error": "Archive timeout."
    }
    response = client.get("/planets/")
    assert response.status_code == 200
    assert response.data.count(b"Data Unavailable") >= 2


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
