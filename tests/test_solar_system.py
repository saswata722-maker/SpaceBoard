from unittest.mock import MagicMock, patch

from requests.exceptions import HTTPError, Timeout

from app.api.solar_system import get_body, get_bodies, get_planets


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


SAMPLE_BODIES = [
    {
        "id": "mercure",
        "name": "Mercure",
        "nameEnglish": "Mercury",
        "isPlanet": True,
        "massMassValue": 3.3,
        "massExp": 23,
        "radiusMean": 2439.7,
        "gravity": 3.7,
        "density": 5.43,
        "escape": 4250.0,
        "semimajorAxis": 57909050,
        "orbitalPeriod": 87.97,
        "moons": [],
        "discoveredBy": None,
        "discoveryDate": None,
    },
    {
        "id": "terre",
        "name": "Terre",
        "nameEnglish": "Earth",
        "isPlanet": True,
        "massMassValue": 5.97,
        "massExp": 24,
        "radiusMean": 6371.0,
        "gravity": 9.81,
        "density": 5.51,
        "escape": 11186.0,
        "semimajorAxis": 149598023,
        "orbitalPeriod": 365.25,
        "moons": [{"moon": "Lune", "rel": ""}],
        "discoveredBy": None,
        "discoveryDate": None,
    },
]

SAMPLE_BODY_EARTH = {
    "id": "terre",
    "name": "Terre",
    "nameEnglish": "Earth",
    "isPlanet": True,
    "massMassValue": 5.97,
    "massExp": 24,
    "radiusMean": 6371.0,
    "gravity": 9.81,
    "density": 5.51,
    "moons": [{"moon": "Lune", "rel": ""}],
    "semimajorAxis": 149598023,
}

BUILTIN_PLANET_NAMES = (
    "Mercury", "Venus", "Earth", "Mars", "Jupiter",
    "Saturn", "Uranus", "Neptune", "Pluto",
)


@patch("app.api.solar_system.requests.get")
def test_get_bodies_success(mock_get):
    mock_get.return_value = _mock_response({"bodies": SAMPLE_BODIES})

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_bodies()

    assert result["ok"] is True
    assert result["error"] is None
    assert len(result["data"]) == 2
    assert result["data"][0]["nameEnglish"] == "Mercury"


@patch("app.api.solar_system.requests.get")
def test_get_bodies_planets_only(mock_get):
    mock_get.return_value = _mock_response({"bodies": SAMPLE_BODIES})

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_bodies(is_planet=True)

    assert result["ok"] is True
    assert len(result["data"]) == 2  # Both samples are planets


@patch("app.api.solar_system.requests.get")
def test_get_bodies_timeout(mock_get):
    mock_get.side_effect = Timeout("Connection timed out")

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_bodies()

    assert result["ok"] is False
    assert "timed out" in result["error"]


@patch("app.api.solar_system.requests.get")
def test_get_bodies_generic_error(mock_get):
    mock_get.side_effect = Exception("Connection refused")

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_bodies()

    assert result["ok"] is False
    assert "Unexpected error" in result["error"]


@patch("app.api.solar_system.requests.get")
def test_get_body_success(mock_get):
    mock_get.return_value = _mock_response(SAMPLE_BODY_EARTH)

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_body("terre")

    assert result["ok"] is True
    assert result["data"]["nameEnglish"] == "Earth"
    assert result["data"]["radiusMean"] == 6371.0


@patch("app.api.solar_system.requests.get")
def test_get_body_timeout(mock_get):
    mock_get.side_effect = Timeout("Connection timed out")

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_body("mars")

    assert result["ok"] is False
    assert "timed out" in result["error"]


# ---------------------------------------------------------------------------
# get_planets(): UI wrapper with a built-in fallback
# ---------------------------------------------------------------------------

@patch("app.api.solar_system.requests.get")
def test_get_planets_live_data_has_no_note(mock_get):
    """When the upstream API answers, planets come straight from it and no
    provenance note is needed."""
    mock_get.return_value = _mock_response({"bodies": SAMPLE_BODIES})

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_planets()

    assert result["ok"] is True
    assert result["error"] is None
    assert result["note"] is None
    assert result["data"] == SAMPLE_BODIES


@patch("app.api.solar_system.requests.get")
def test_get_planets_falls_back_to_builtin_on_401(mock_get):
    """The OpenData API now needs a bearer token; without one it 401s, so the
    card grid must still get the nine built-in planets plus a provenance note."""
    mock_get.return_value = _mock_response({}, status_code=401)

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_planets()

    assert result["ok"] is True
    assert result["error"] is None
    assert result["note"] is not None
    names = [b["nameEnglish"] for b in result["data"]]
    for want in BUILTIN_PLANET_NAMES:
        assert want in names


@patch("app.api.solar_system.requests.get")
def test_get_planets_builtin_shape_matches_template(mock_get):
    """Every fallback planet carries the fields planets.html dereferences and an
    English name the tonight script can map to an astronomy-engine Body."""
    mock_get.side_effect = Timeout("Connection timed out")

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        result = get_planets()

    assert len(result["data"]) == len(BUILTIN_PLANET_NAMES)
    for body in result["data"]:
        assert body["nameEnglish"]
        assert body["massMassValue"] is not None
        assert body["massExp"] is not None
        assert body["radiusMean"] is not None
        assert body["gravity"] is not None
        assert body["orbitalPeriod"] is not None
        assert isinstance(body["moons"], list)
