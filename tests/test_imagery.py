import logging
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import ConnectionError, HTTPError, Timeout

from app.api.imagery import get_body_image


METADATA = {
    "nasa_id": "PIA00001",
    "title": "Mars in True Color",
    "center": "JPL",
    "date_created": "2024-03-01T00:00:00Z",
    "secondary_creator": "NASA/JPL-Caltech",
    "media_type": "image",
    "description": "Mars in true color.",
}

CANONICAL_LINK = {
    "href": "https://images-assets.nasa.gov/image/PIA00001~orig.jpg",
    "rel": "canonical",
    "render": "image",
}

PREVIEW_LINK = {
    "href": "https://images-assets.nasa.gov/image/PIA00001~medium.jpg",
    "rel": "preview",
    "render": "image",
}

NASA_SEARCH_URL = "https://images-api.nasa.gov/search"

COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"


def _app():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app


def _search_response(payload, status_code=200):
    mock = MagicMock()
    mock.json.return_value = payload
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        mock.raise_for_status.side_effect = HTTPError(response=mock)
    return mock


def _commons_response(payload, status_code=200):
    """Mock response for Wikimedia Commons API calls."""
    mock = MagicMock()
    mock.json.return_value = payload
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        mock.raise_for_status.side_effect = HTTPError(response=mock)
    return mock


def _by_url(nasa_payload, commons_payload):
    """Serve both APIs from one patched ``requests.get``.

    ``app.api.commons.requests`` and ``app.api.images.requests`` are the same
    module, so a single transport patch sees every call; each endpoint is
    answered with its own payload, exactly as in production.
    """

    def _get(url, **kwargs):
        if url == NASA_SEARCH_URL:
            return _search_response(nasa_payload)
        return _commons_response(commons_payload)

    return _get


def _payload(items):
    return {"collection": {"items": items, "metadata": {"total_hits": len(items)}}}


def _item(links=None, metadata=None):
    return {
        "data": [METADATA if metadata is None else metadata],
        "links": [PREVIEW_LINK, CANONICAL_LINK] if links is None else links,
    }


def _href_link(href):
    return {"href": href, "rel": "canonical", "render": "image"}


def _commons_file(pageid, title, url, index):
    """A Commons file page: a web image, public domain, naming the subject."""
    return {
        "pageid": pageid,
        "ns": 6,
        "title": title,
        "index": index,
        "imagerepository": "local",
        "imageinfo": [
            {
                "url": url,
                "descriptionurl": f"https://commons.wikimedia.org/wiki/File:{title}",
                "extmetadata": {
                    "Copyrighted": {"value": "False", "source": "mediawiki-metadata", "hidden": ""},
                    "LicenseShortName": {"value": "Public domain", "source": "mediawiki-metadata", "hidden": ""},
                    "Artist": {"value": "NASA/JPL-Caltech", "source": "mediawiki-metadata"},
                },
            }
        ],
    }


def _commons_payload(files):
    return {"query": {"pages": {str(file["pageid"]): file for file in files}}}


def _get_body_image_with_cleared_cache(name="Mars", hostname=None):
    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        return get_body_image(name, hostname=hostname)


# ---------------------------------------------------------------------------
# Core behaviour
# ---------------------------------------------------------------------------


@patch("app.api.images.requests.get")
def test_body_image_searches_library_by_body_name(mock_get):
    """The name is qualified with "planet": the library is a full-text
    search, and a bare "Mars" returns event photos of a town in Pennsylvania
    before it returns pictures of the planet."""
    mock_get.return_value = _search_response(_payload([_item()]))

    result = _get_body_image_with_cleared_cache("Mars")

    assert mock_get.call_count == 1
    args, kwargs = mock_get.call_args
    assert args[0] == NASA_SEARCH_URL
    assert kwargs["params"] == {"q": "Mars planet", "media_type": "image"}
    assert result["ok"] is True


@patch("app.api.images.requests.get")
def test_canonical_rendition_is_preferred(mock_get):
    mock_get.return_value = _search_response(_payload([_item()]))

    result = _get_body_image_with_cleared_cache("Mars")

    assert result["data"]["url"] == CANONICAL_LINK["href"]


@patch("app.api.images.requests.get")
def test_body_image_is_normalised(mock_get):
    mock_get.return_value = _search_response(_payload([_item()]))

    result = _get_body_image_with_cleared_cache("Mars")

    assert set(result["data"]) == {"url", "title", "credit", "nasa_id", "provider"}
    assert result["data"] == {
        "url": CANONICAL_LINK["href"],
        "title": "Mars in True Color",
        "credit": "NASA/JPL-Caltech",
        "nasa_id": "PIA00001",
        "provider": "NASA Image and Video Library",
    }


@patch("app.api.images.requests.get")
def test_credit_prefers_secondary_creator(mock_get):
    mock_get.return_value = _search_response(_payload([_item()]))

    result = _get_body_image_with_cleared_cache("Mars")

    assert result["data"]["credit"] == "NASA/JPL-Caltech"


@patch("app.api.images.requests.get")
def test_tif_canonical_falls_back_to_largest_web_rendition(mock_get):
    links = [
        {"href": "https://images-assets.nasa.gov/image/PIA00001~medium.jpg",
         "rel": "alternate", "render": "image"},
        {"href": "https://images-assets.nasa.gov/image/PIA00001~large.jpg",
         "rel": "alternate", "render": "image"},
        {"href": "https://images-assets.nasa.gov/image/PIA00001~orig.tif",
         "rel": "canonical", "render": "image"},
    ]
    mock_get.return_value = _search_response(_payload([_item(links=links)]))

    result = _get_body_image_with_cleared_cache("Mars")

    assert result["data"]["url"] == "https://images-assets.nasa.gov/image/PIA00001~large.jpg"


@patch("app.api.images.requests.get")
def test_credit_falls_back_to_center(mock_get):
    metadata = {k: v for k, v in METADATA.items() if k != "secondary_creator"}
    mock_get.return_value = _search_response(_payload([_item(metadata=metadata)]))

    result = _get_body_image_with_cleared_cache("Mars")

    assert result["data"]["credit"] == "JPL"


@patch("app.api.images.requests.get")
def test_no_usable_image_degrades_to_none(mock_get):
    """NASA has nothing usable and Commons has no eligible file, so the body
    degrades to its text-only layout: an absent image is not an error."""
    mock_get.side_effect = _by_url(_payload([]), _commons_payload([]))

    result = _get_body_image_with_cleared_cache("Kepler-22 b")

    assert result["ok"] is True
    assert result["data"] is None
    assert result["error"] is None


@pytest.mark.parametrize(
    "side_effect",
    [
        HTTPError(response=MagicMock(status_code=500)),
        Timeout("Connection timed out"),
        ConnectionError("Connection refused"),
    ],
    ids=["http-500", "timeout", "connection-error"],
)
@patch("app.api.images.requests.get")
def test_transport_failures_are_caught_never_raised(mock_get, side_effect, caplog):
    """Every source down is graceful degradation, not an error envelope: the
    page renders without a hero image, and each failure is logged."""
    mock_get.side_effect = side_effect

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        with caplog.at_level(logging.WARNING):
            result = get_body_image("Mars")

    assert result["ok"] is True
    assert result["data"] is None
    assert result["error"] is None
    assert any(r.levelno >= logging.WARNING for r in caplog.records)


@pytest.mark.parametrize("name", [None, "", "   "])
def test_blank_name_short_circuits_without_a_search(name):
    result = _get_body_image_with_cleared_cache(name)

    assert result["ok"] is True
    assert result["data"] is None


@patch("app.api.images.requests.get")
def test_search_is_memoized(mock_get):
    mock_get.return_value = _search_response(_payload([_item()]))

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        first = get_body_image("Mars")
        second = get_body_image("Mars")

    assert mock_get.call_count == 1
    assert first["data"]["url"] == second["data"]["url"]


# ---------------------------------------------------------------------------
# Relevance: the image must depict the subject body
# ---------------------------------------------------------------------------


def _record(title, description="A NASA image.", links=None, **extra):
    metadata = {"nasa_id": "PIA00002", "title": title,
                "center": "JPL", "date_created": "2024-03-01T00:00:00Z",
                "description": description}
    metadata.update(extra)
    return {"data": [metadata], "links": [CANONICAL_LINK] if links is None else links}


@patch("app.api.images.requests.get")
def test_record_that_does_not_name_the_body_is_skipped(mock_get):
    """A hit that never names the subject is not an image of it."""
    mock_get.return_value = _search_response(_payload([
        _record("A Busy Day at the Jet Propulsion Laboratory"),
        _record("Engineers Review a Rover Design"),
    ]))

    result = _get_body_image_with_cleared_cache("Mars")

    assert result["ok"] is True
    assert result["data"] is None


@patch("app.api.images.requests.get")
def test_record_about_a_different_body_is_skipped(mock_get):
    """"Europa, taken from Voyager 1 to Jupiter" pictures Europa, not Jupiter."""
    mock_get.return_value = _search_response(_payload([
        _record("Europa, taken from Voyager 1 to Jupiter"),
        _record("Voyager Picture of Jupiter"),
    ]))

    result = _get_body_image_with_cleared_cache("Jupiter")

    assert result["data"]["title"] == "Voyager Picture of Jupiter"


@patch("app.api.images.requests.get")
def test_photograph_is_preferred_over_a_visualisation(mock_get):
    mock_get.return_value = _search_response(_payload([
        _record("Mars in the Future - Artist Concept",
                description="An artist's concept of Mars."),
        _record("Composite image of the planet Mars"),
    ]))

    result = _get_body_image_with_cleared_cache("Mars")

    assert result["data"]["title"] == "Composite image of the planet Mars"


@patch("app.api.images.requests.get")
def test_visualisation_is_accepted_when_no_photograph_exists(mock_get):
    """For most exoplanets an artist's concept is NASA's authentic imagery of
    the body, and better than degrading when it names the subject."""
    mock_get.return_value = _search_response(_payload([
        _record("TRAPPIST-1 Planet Lineup",
                description="This artist's concept shows the TRAPPIST-1 system."),
    ]))

    result = _get_body_image_with_cleared_cache("TRAPPIST-1e")

    assert result["data"]["title"] == "TRAPPIST-1 Planet Lineup"


@patch("app.api.images.requests.get")
def test_exoplanet_matches_its_system_designation(mock_get):
    """Imagery of "TRAPPIST-1e" is filed under the system, "TRAPPIST-1"."""
    mock_get.return_value = _search_response(_payload([
        _record("TRAPPIST-1 System - Artist Concept",
                description="An artist's concept of the TRAPPIST-1 system."),
    ]))

    result = _get_body_image_with_cleared_cache("TRAPPIST-1e")

    assert result["data"]["title"] == "TRAPPIST-1 System - Artist Concept"


@patch("app.api.images.requests.get")
def test_event_photo_sharing_the_name_is_not_the_body(mock_get):
    """NASA's "Mars Celebration" is a photo of a festival in the town of
    Mars, Pennsylvania — the query qualification normally keeps it out, and
    the markers reject it if it ever surfaces."""
    mock_get.return_value = _search_response(_payload([
        _record("Mars Celebration",
                description="The Mars celebration in Mars, Pennsylvania."),
        _record("Springtime on Mars: Hubble Best View of the Red Planet"),
    ]))

    result = _get_body_image_with_cleared_cache("Mars")

    assert result["data"]["title"] == (
        "Springtime on Mars: Hubble Best View of the Red Planet"
    )


@patch("app.api.images.requests.get")
def test_subject_named_after_another_body_in_title_is_rejected(mock_get):
    """"A Portrait of Planet and Moon: ... Jupiter and Io" is a Jupiter
    picture even though Io is named in the title too."""
    mock_get.return_value = _search_response(_payload([
        _record("A Portrait of Planet and Moon: NASA's Juno Mission Captures "
                "Jupiter and Io Together"),
    ]))

    result = _get_body_image_with_cleared_cache("Jupiter")

    assert result["data"]["title"].endswith("Jupiter and Io Together")


# ---------------------------------------------------------------------------
# Daily rotation: the same body shows a different image each day
# ---------------------------------------------------------------------------


MARS_PHOTOS = _payload([
    _record("Mars Photo One", links=[_href_link(
        "https://images-assets.nasa.gov/image/PIA00011~orig.jpg")]),
    _record("Mars Photo Two", links=[_href_link(
        "https://images-assets.nasa.gov/image/PIA00012~orig.jpg")]),
    _record("Mars Photo Three", links=[_href_link(
        "https://images-assets.nasa.gov/image/PIA00013~orig.jpg")]),
])


def _pick_for_days(days):
    """The image ``get_body_image`` returns for each of *days*."""
    picked = {}
    app = _app()
    with app.app_context():
        from app.api import imagery
        from app.cache import cache

        cache.clear()
        for day in days:
            with patch("app.api.imagery._day_index", return_value=day):
                picked[day] = get_body_image("Mars")["data"]["url"]
    return picked


@patch("app.api.images.requests.get")
def test_image_rotates_by_day_index_and_is_stable_within_a_day(mock_get):
    mock_get.return_value = _search_response(MARS_PHOTOS)

    picked = _pick_for_days([0, 1, 0])

    assert len({picked[0], picked[1]}) == 2
    assert picked[0] == MARS_PHOTOS["collection"]["items"][0]["links"][0]["href"]
    assert picked[1] == MARS_PHOTOS["collection"]["items"][1]["links"][0]["href"]


@patch("app.api.images.requests.get")
def test_day_index_wraps_across_the_eligible_images(mock_get):
    mock_get.return_value = _search_response(MARS_PHOTOS)

    picked = _pick_for_days([0, 1, 2, 3, 4, 5])

    # Three eligible images: index 0, 3 share; 1, 4 share; 2, 5 share.
    assert picked[0] == picked[3]
    assert picked[1] == picked[4]
    assert picked[2] == picked[5]
    assert len({picked[0], picked[1], picked[2]}) == 3


@patch("app.api.images.requests.get")
def test_single_eligible_image_stays_fixed_across_days(mock_get):
    mock_get.return_value = _search_response(_payload([_item()]))

    picked = _pick_for_days([0, 1, 2])

    assert set(picked.values()) == {CANONICAL_LINK["href"]}


@patch("app.api.images.requests.get")
def test_commons_fallback_rotates_by_day_index(mock_get):
    """The Commons fallback rotates too: NASA has nothing, and the body
    walks Commons' eligible files by the day's index."""
    files = [
        _commons_file(1, "File:Kepler-22b_Artist%27s_Impression.png",
                      "https://upload.wikimedia.org/wikipedia/commons/5/5f/Kepler22b_one.png", 1),
        _commons_file(2, "File:Kepler-22b_Surface.jpg",
                      "https://upload.wikimedia.org/wikipedia/commons/2/2f/Kepler22b_two.jpg", 2),
        _commons_file(3, "File:Kepler-22b_System_View.jpg",
                      "https://upload.wikimedia.org/wikipedia/commons/3/3f/Kepler22b_three.jpg", 3),
    ]
    mock_get.side_effect = _by_url(_payload([]), _commons_payload(files))

    picked = {}
    app = _app()
    with app.app_context():
        from app.api import imagery
        from app.cache import cache

        cache.clear()
        for day in (0, 1, 2):
            with patch("app.api.imagery._day_index", return_value=day):
                picked[day] = get_body_image("Kepler-22 b")["data"]["url"]

    assert picked[0] == "https://upload.wikimedia.org/wikipedia/commons/5/5f/Kepler22b_one.png"
    assert picked[1] == "https://upload.wikimedia.org/wikipedia/commons/2/2f/Kepler22b_two.jpg"
    assert picked[2] == "https://upload.wikimedia.org/wikipedia/commons/3/3f/Kepler22b_three.jpg"
