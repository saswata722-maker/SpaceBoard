from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import ConnectionError, HTTPError, Timeout

from app.api.images import (
    FALLBACK_QUERY,
    IMAGES_API_URL,
    PROVIDER_NAME,
    get_fallback_image,
    search_images,
)


METADATA = {
    "nasa_id": "PIA00001",
    "title": "A Featured Nebula",
    "center": "JPL",
    "date_created": "2024-03-01T00:00:00Z",
    "secondary_creator": "NASA/JPL-Caltech",
    "media_type": "image",
    "description": "A featured nebula image from the library.",
}

CANONICAL_LINK = {
    "href": "https://images-api.nasa.gov/image/PIA00001~orig.jpg",
    "rel": "canonical",
    "render": "image",
}

PREVIEW_LINK = {
    "href": "https://images-api.nasa.gov/image/PIA00001~medium.jpg",
    "rel": "preview",
    "render": "image",
}


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


def _payload(items):
    return {"collection": {"items": items, "metadata": {"total_hits": len(items)}}}


def _item(links=None, metadata=None):
    return {
        "data": [METADATA if metadata is None else metadata],
        "links": [PREVIEW_LINK, CANONICAL_LINK] if links is None else links,
    }


def _get_fallback_image_with_cleared_cache():
    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        return get_fallback_image()


@patch("app.api.images.requests.get")
def test_fallback_image_hits_library_with_pinned_query(mock_get):
    mock_get.return_value = _search_response(_payload([_item()]))

    result = _get_fallback_image_with_cleared_cache()

    assert mock_get.call_count == 1
    args, kwargs = mock_get.call_args
    assert args[0] == IMAGES_API_URL
    assert kwargs["params"] == {"q": FALLBACK_QUERY, "media_type": "image"}
    assert kwargs["timeout"] == 15
    assert result["ok"] is True
    assert result["error"] is None


@patch("app.api.images.requests.get")
def test_canonical_rendition_is_preferred(mock_get):
    mock_get.return_value = _search_response(_payload([_item()]))

    result = _get_fallback_image_with_cleared_cache()

    assert result["data"]["url"] == CANONICAL_LINK["href"]


@patch("app.api.images.requests.get")
def test_first_image_link_used_when_no_canonical(mock_get):
    mock_get.return_value = _search_response(_payload([_item(links=[PREVIEW_LINK])]))

    result = _get_fallback_image_with_cleared_cache()

    assert result["data"]["url"] == PREVIEW_LINK["href"]


@patch("app.api.images.requests.get")
def test_tif_canonical_falls_back_to_largest_web_rendition(mock_get):
    """The canonical file of many NASA records is a ``~orig.tif`` that no
    browser can render; the largest web rendition is used instead."""
    links = [
        {"href": "https://images-api.nasa.gov/image/PIA00001~thumb.jpg",
         "rel": "preview", "render": "image"},
        {"href": "https://images-api.nasa.gov/image/PIA00001~medium.jpg",
         "rel": "alternate", "render": "image"},
        {"href": "https://images-api.nasa.gov/image/PIA00001~large.jpg",
         "rel": "alternate", "render": "image"},
        {"href": "https://images-api.nasa.gov/image/PIA00001~orig.tif",
         "rel": "canonical", "render": "image"},
    ]
    mock_get.return_value = _search_response(_payload([_item(links=links)]))

    result = _get_fallback_image_with_cleared_cache()

    assert result["data"]["url"] == "https://images-api.nasa.gov/image/PIA00001~large.jpg"


@patch("app.api.images.requests.get")
def test_web_canonical_still_wins_over_smaller_renditions(mock_get):
    links = [
        {"href": "https://images-api.nasa.gov/image/PIA00001~large.jpg",
         "rel": "alternate", "render": "image"},
        {"href": "https://images-api.nasa.gov/image/PIA00001~orig.jpg",
         "rel": "canonical", "render": "image"},
    ]
    mock_get.return_value = _search_response(_payload([_item(links=links)]))

    result = _get_fallback_image_with_cleared_cache()

    assert result["data"]["url"] == "https://images-api.nasa.gov/image/PIA00001~orig.jpg"


@patch("app.api.images.requests.get")
def test_non_web_only_renditions_degrade_to_no_image(mock_get):
    """A record whose only rendition is a TIFF renders nothing, so the page
    degrades rather than showing a broken image."""
    links = [
        {"href": "https://images-api.nasa.gov/image/PIA00001~orig.tif",
         "rel": "canonical", "render": "image"},
    ]
    mock_get.return_value = _search_response(_payload([_item(links=links)]))

    result = _get_fallback_image_with_cleared_cache()

    assert result["ok"] is True
    assert result["data"] is None


@patch("app.api.images.requests.get")
def test_empty_search_results_are_not_an_error(mock_get):
    mock_get.return_value = _search_response(_payload([]))

    result = _get_fallback_image_with_cleared_cache()

    assert result["ok"] is True
    assert result["data"] is None
    assert result["error"] is None


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        [],
        {"collection": None},
        {"collection": {}},
        {"collection": {"items": None}},
        {"collection": {"items": []}},
        {"collection": {"items": [{}]}},
        {"collection": {"items": [_item(links=[])]}},
        {"collection": {"items": [_item(links=[{"rel": "canonical", "render": "image", "href": "x.tif"}])]}},
        {"collection": {"items": [_item(links=[{"rel": "preview", "render": "image", "href": ""}])]}},
        {"collection": {"items": [_item(links=[{"rel": "alternate", "render": "video", "href": "x"}])]}},
        {"collection": {"items": [_item(metadata={"title": "No id"})]}},
        {"collection": {"items": [_item(metadata={"nasa_id": "PIA00001"})]}},
        {"collection": {"items": [{}, _item()]}},
    ],
)
@patch("app.api.images.requests.get")
def test_degenerate_payloads_yield_no_image_without_raising(mock_get, payload):
    mock_get.return_value = _search_response(payload)

    result = _get_fallback_image_with_cleared_cache()

    assert result["ok"] is True
    assert result["data"] is None


@patch("app.api.images.requests.get")
def test_http_error_returns_fail_envelope(mock_get):
    mock_get.return_value = _search_response({}, status_code=500)

    result = _get_fallback_image_with_cleared_cache()

    assert result["ok"] is False
    assert result["data"] is None
    assert "HTTP 500" in result["error"]


@pytest.mark.parametrize(
    "side_effect",
    [
        Timeout("Connection timed out"),
        ConnectionError("Connection refused"),
    ],
    ids=["timeout", "connection-error"],
)
@patch("app.api.images.requests.get")
def test_transport_errors_return_fail_envelope(mock_get, side_effect):
    mock_get.side_effect = side_effect

    result = _get_fallback_image_with_cleared_cache()

    assert result["ok"] is False
    assert result["data"] is None
    assert result["error"]


@patch("app.api.images.requests.get")
def test_fallback_data_is_normalised_with_native_attribution(mock_get):
    mock_get.return_value = _search_response(_payload([_item()]))

    result = _get_fallback_image_with_cleared_cache()

    assert result["data"] == {
        "url": CANONICAL_LINK["href"],
        "media_type": "image",
        "title": "A Featured Nebula",
        "date": "2024-03-01",
        "copyright": "NASA/JPL-Caltech",
        "source": PROVIDER_NAME,
        "nasa_id": "PIA00001",
    }


@patch("app.api.images.requests.get")
def test_copyright_falls_back_to_center(mock_get):
    metadata = {k: v for k, v in METADATA.items() if k != "secondary_creator"}
    mock_get.return_value = _search_response(_payload([_item(metadata=metadata)]))

    result = _get_fallback_image_with_cleared_cache()

    assert result["data"]["copyright"] == "JPL"


@patch("app.api.images.requests.get")
def test_search_is_memoized(mock_get):
    mock_get.return_value = _search_response(_payload([_item()]))

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        first = get_fallback_image()
        second = get_fallback_image()

    assert mock_get.call_count == 1
    assert first["data"]["url"] == second["data"]["url"]


# ---------------------------------------------------------------------------
# search_images: every usable image, in relevance order
# ---------------------------------------------------------------------------


def _titled_item(title, href):
    return _item(
        links=[{"href": href, "rel": "canonical", "render": "image"}],
        metadata={**METADATA, "title": title},
    )


def _get_images_with_cleared_cache(query="Jupiter planet", accept=None):
    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        return search_images(query, accept=accept)


THREE_IMAGES = _payload([
    _titled_item("Jupiter's Swirling South Pole",
                 "https://images-api.nasa.gov/image/PIA00011~orig.jpg"),
    _titled_item("Jupiter in True Color",
                 "https://images-api.nasa.gov/image/PIA00012~orig.jpg"),
    _titled_item("Voyager Picture of Jupiter",
                 "https://images-api.nasa.gov/image/PIA00013~orig.jpg"),
])


@patch("app.api.images.requests.get")
def test_search_images_returns_every_usable_image_in_relevance_order(mock_get):
    mock_get.return_value = _search_response(THREE_IMAGES)

    result = _get_images_with_cleared_cache()

    assert result["ok"] is True
    assert result["error"] is None
    assert [image["href"] for image in result["data"]] == [
        "https://images-api.nasa.gov/image/PIA00011~orig.jpg",
        "https://images-api.nasa.gov/image/PIA00012~orig.jpg",
        "https://images-api.nasa.gov/image/PIA00013~orig.jpg",
    ]


@patch("app.api.images.requests.get")
def test_search_images_honours_accept(mock_get):
    mock_get.return_value = _search_response(THREE_IMAGES)

    result = _get_images_with_cleared_cache(
        accept=lambda metadata: metadata["title"] == "Jupiter in True Color"
    )

    assert result["ok"] is True
    assert [image["metadata"]["title"] for image in result["data"]] == [
        "Jupiter in True Color"
    ]


@patch("app.api.images.requests.get")
def test_search_images_empty_results_are_not_an_error(mock_get):
    mock_get.return_value = _search_response(_payload([]))

    result = _get_images_with_cleared_cache()

    assert result["ok"] is True
    assert result["data"] == []
    assert result["error"] is None


@pytest.mark.parametrize(
    "side_effect",
    [
        Timeout("Connection timed out"),
        ConnectionError("Connection refused"),
    ],
    ids=["timeout", "connection-error"],
)
@patch("app.api.images.requests.get")
def test_search_images_transport_errors_return_fail_envelope(mock_get, side_effect):
    mock_get.side_effect = side_effect

    result = _get_images_with_cleared_cache()

    assert result["ok"] is False
    assert result["data"] is None
    assert result["error"]


@patch("app.api.images.requests.get")
def test_search_images_http_error_returns_fail_envelope(mock_get):
    mock_get.return_value = _search_response({}, status_code=500)

    result = _get_images_with_cleared_cache()

    assert result["ok"] is False
    assert result["data"] is None
    assert "HTTP 500" in result["error"]
