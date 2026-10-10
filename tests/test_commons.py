import json
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import ConnectionError, HTTPError, Timeout

from app.api.commons import search_commons_image, search_commons_images


# ---------- Fixtures ----------

CANONICAL = {
    "url": "https://upload.wikimedia.org/wikipedia/commons/5/5f/TRAPPIST-1e_Artist%27s_Impression.png",
    "title": "TRAPPIST-1e Artist's Impression",
    "credit": "NASA/JPL-Caltech",
    "license": "Public domain",
    "file_page_url": "https://commons.wikimedia.org/wiki/File:TRAPPIST-1e_Artist%27s_Impression.png",
    "provider": "Wikimedia Commons",
}


def _app():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app


def _commons_response(payload, status_code=200):
    mock = MagicMock()
    mock.json.return_value = payload
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        mock.raise_for_status.side_effect = HTTPError(response=mock)
    return mock


def _payload(items):
    """A minimal Commons generator=search response structure."""
    pages = {}
    for idx, item in enumerate(items):
        pages[str(item["pageid"])] = item
    return {"query": {"pages": pages}}


def _item(pageid, title, url, extmetadata=None, index=1):
    """A single file page with imageinfo."""
    ext = extmetadata or {}
    defaults = {
        "Copyrighted": {"value": "False", "source": "mediawiki-metadata", "hidden": ""},
        "LicenseShortName": {"value": "Public domain", "source": "mediawiki-metadata", "hidden": ""},
        "Artist": {"value": "NASA/JPL-Caltech", "source": "mediawiki-metadata"},
        "Credit": {"value": "", "source": "mediawiki-metadata"},
    }
    ext.update(defaults)
    return {
        "pageid": pageid,
        "ns": 6,
        "title": title,
        "index": index,
        "imagerepository": "local",
        "imageinfo": [
            {
                "url": url,
                "descriptionurl": f"https://commons.wikimedia.org/wiki/File:{title.replace(' ', '_')}",
                "extmetadata": ext,
            },
        ],
    }


def _get_commons_image_with_cleared_cache(query="TRAPPIST-1e exoplanet", designation="TRAPPIST-1e"):
    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        return search_commons_image(query, designation)


def _get_commons_images_with_cleared_cache(query="TRAPPIST-1e exoplanet", designation="TRAPPIST-1e"):
    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        return search_commons_images(query, designation)


# ---------------------------------------------------------------------------
# Core behaviour
# ---------------------------------------------------------------------------


@patch("app.api.commons.requests.get")
def test_commons_image_hits_commons_with_query_and_limit(mock_get):
    mock_get.return_value = _commons_response(
        {
            "batchcomplete": "",
            "query": {"pages": {}},
        }
    )

    result = _get_commons_image_with_cleared_cache("TRAPPIST-1e exoplanet", "TRAPPIST-1e")

    assert mock_get.call_count == 1
    args, kwargs = mock_get.call_args
    assert args[0] == "https://commons.wikimedia.org/w/api.php"
    assert kwargs["params"]["gsrsearch"] == "TRAPPIST-1e exoplanet"
    assert kwargs["params"]["gsrnamespace"] == 6
    assert kwargs["params"]["gsrlimit"] == 10
    assert kwargs["params"]["prop"] == "imageinfo"
    assert kwargs["params"]["iiprop"] == "url|extmetadata"
    assert kwargs["params"]["generator"] == "search"
    assert result["ok"] is True
    assert result["error"] is None


@patch("app.api.commons.requests.get")
def test_canonical_pd_image_is_preferred(mock_get):
    """First result that is a web image, PD, and names the subject wins."""
    mock_get.return_value = _commons_response(
        {
            "query": {
                "pages": {
                    "1": {
                        "pageid": 1,
                        "ns": 6,
                        "title": "File:TRAPPIST-1e_Artist%27s_Impression.png",
                        "index": 1,
                        "imagerepository": "local",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/wikipedia/commons/5/5f/TRAPPIST-1e_Artist%27s_Impression.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:TRAPPIST-1e_Artist%27s_Impression.png",
                                "extmetadata": {
                                    "Copyrighted": {"value": "False", "source": "mediawiki-metadata", "hidden": ""},
                                    "LicenseShortName": {"value": "Public domain", "source": "mediawiki-metadata", "hidden": ""},
                                    "Artist": {"value": "NASA/JPL-Caltech", "source": "mediawiki-metadata"},
                                    "Credit": {"value": "", "source": "mediawiki-metadata"},
                                },
                            },
                        ],
                    },
                    "2": {
                        "pageid": 2,
                        "ns": 6,
                        "title": "File:TRAPPIST-1_System_Overview.jpg",
                        "index": 2,
                        "imagerepository": "local",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/wikipedia/commons/2/2f/TRAPPIST-1_System_Overview.jpg",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:TRAPPIST-1_System_Overview.jpg",
                                "extmetadata": {
                                    "Copyrighted": {"value": "False", "source": "mediawiki-metadata", "hidden": ""},
                                    "LicenseShortName": {"value": "Public domain", "source": "mediawiki-metadata", "hidden": ""},
                                    "Artist": {"value": "NASA/JPL-Caltech", "source": "mediawiki-metadata"},
                                    "Credit": {"value": "", "source": "mediawiki-metadata"},
                                },
                            },
                        ],
                    },
                }
            }
        }
    )

    result = _get_commons_image_with_cleared_cache("TRAPPIST-1e exoplanet", "TRAPPIST-1e")

    assert result["ok"] is True
    assert result["data"]["title"] == "TRAPPIST-1e Artist's Impression"
    assert result["data"]["credit"] == "NASA/JPL-Caltech"
    assert result["data"]["license"] == "Public domain"
    assert result["data"]["provider"] == "Wikimedia Commons"
    assert "TRAPPIST-1e_Artist" in result["data"]["url"]
    assert "utm_" not in result["data"]["url"]


@patch("app.api.commons.requests.get")
def test_search_commons_images_returns_every_eligible_file_in_order(mock_get):
    """The list variant keeps every eligible file in search order, so the
    caller can rotate a daily index across them."""
    mock_get.return_value = _commons_response(
        {
            "query": {
                "pages": {
                    "1": {
                        "pageid": 1,
                        "ns": 6,
                        "title": "File:TRAPPIST-1e_Artist%27s_Impression.png",
                        "index": 1,
                        "imagerepository": "local",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/wikipedia/commons/5/5f/TRAPPIST-1e_Artist%27s_Impression.png",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:TRAPPIST-1e_Artist%27s_Impression.png",
                                "extmetadata": {
                                    "Copyrighted": {"value": "False", "source": "mediawiki-metadata", "hidden": ""},
                                    "LicenseShortName": {"value": "Public domain", "source": "mediawiki-metadata", "hidden": ""},
                                    "Artist": {"value": "NASA/JPL-Caltech", "source": "mediawiki-metadata"},
                                },
                            },
                        ],
                    },
                    "2": {
                        "pageid": 2,
                        "ns": 6,
                        "title": "File:TRAPPIST-1e_Surface.jpg",
                        "index": 2,
                        "imagerepository": "local",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/wikipedia/commons/2/2f/TRAPPIST-1e_Surface.jpg",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:TRAPPIST-1e_Surface.jpg",
                                "extmetadata": {
                                    "Copyrighted": {"value": "False", "source": "mediawiki-metadata", "hidden": ""},
                                    "LicenseShortName": {"value": "Public domain", "source": "mediawiki-metadata", "hidden": ""},
                                    "Artist": {"value": "NASA/JPL-Caltech", "source": "mediawiki-metadata"},
                                },
                            },
                        ],
                    },
                    "3": {
                        "pageid": 3,
                        "ns": 6,
                        "title": "File:TRAPPIST-1e.tif",
                        "index": 3,
                        "imagerepository": "local",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/wikipedia/commons/3/3f/TRAPPIST-1e.tif",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:TRAPPIST-1e.tif",
                                "extmetadata": {
                                    "Copyrighted": {"value": "False", "source": "mediawiki-metadata", "hidden": ""},
                                    "LicenseShortName": {"value": "Public domain", "source": "mediawiki-metadata", "hidden": ""},
                                    "Artist": {"value": "NASA", "source": "mediawiki-metadata"},
                                },
                            },
                        ],
                    },
                }
            }
        }
    )

    result = _get_commons_images_with_cleared_cache("TRAPPIST-1e exoplanet", "TRAPPIST-1e")

    assert result["ok"] is True
    # The .tif renders in no browser, so only the two web images survive.
    assert [file["url"] for file in result["data"]] == [
        "https://upload.wikimedia.org/wikipedia/commons/5/5f/TRAPPIST-1e_Artist%27s_Impression.png",
        "https://upload.wikimedia.org/wikipedia/commons/2/2f/TRAPPIST-1e_Surface.jpg",
    ]


@patch("app.api.commons.requests.get")
def test_non_web_extensions_are_skipped(mock_get):
    mock_get.return_value = _commons_response(
        {
            "query": {
                "pages": {
                    "1": {
                        "pageid": 1,
                        "ns": 6,
                        "title": "File:Kepler22b.tif",
                        "index": 1,
                        "imagerepository": "local",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/wikipedia/commons/0/00/Kepler22b.tif",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Kepler22b.tif",
                                "extmetadata": {
                                    "Copyrighted": {"value": "False", "source": "mediawiki-metadata", "hidden": ""},
                                    "LicenseShortName": {"value": "Public domain", "source": "mediawiki-metadata", "hidden": ""},
                                    "Artist": {"value": "NASA", "source": "mediawiki-metadata"},
                                },
                            },
                        ],
                    },
                    "2": {
                        "pageid": 2,
                        "ns": 6,
                        "title": "File:Kepler22b.png",
                        "index": 2,
                        "imagerepository": "local",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/wikipedia/commons/0/03/Kepler22b.png",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Kepler22b.png",
                                "extmetadata": {
                                    "Copyrighted": {"value": "False", "source": "mediawiki-metadata", "hidden": ""},
                                    "LicenseShortName": {"value": "Public domain", "source": "mediawiki-metadata", "hidden": ""},
                                    "Artist": {"value": "NASA", "source": "mediawiki-metadata"},
                                },
                            },
                        ],
                    },
                }
            }
        }
    )

    result = _get_commons_image_with_cleared_cache("Kepler-22b exoplanet", "Kepler-22b")

    assert result["data"]["title"] == "Kepler22b"
    assert result["data"]["url"].endswith(".png")


@patch("app.api.commons.requests.get")
def test_cc_by_sa_is_rejected(mock_get):
    """CC BY-SA files are not free for reuse as hero images."""
    mock_get.return_value = _commons_response(
        {
            "query": {
                "pages": {
                    "1": {
                        "pageid": 1,
                        "ns": 6,
                        "title": "File:Kepler22b_artist_concept.jpg",
                        "index": 1,
                        "imagerepository": "local",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/wikipedia/commons/0/00/Kepler22b_artist_concept.jpg",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Kepler22b_artist_concept.jpg",
                                "extmetadata": {
                                    "Copyrighted": {"value": "True", "source": "mediawiki-metadata", "hidden": ""},
                                    "LicenseShortName": {"value": "CC BY-SA 4.0", "source": "mediawiki-metadata", "hidden": ""},
                                    "Artist": {"value": "Some Artist", "source": "mediawiki-metadata"},
                                },
                            },
                        ],
                    },
                    "2": {
                        "pageid": 2,
                        "ns": 6,
                        "title": "File:Kepler22b_pd.jpg",
                        "index": 2,
                        "imagerepository": "local",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/wikipedia/commons/0/03/Kepler22b_pd.jpg",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Kepler22b_pd.jpg",
                                "extmetadata": {
                                    "Copyrighted": {"value": "False", "source": "mediawiki-metadata", "hidden": ""},
                                    "LicenseShortName": {"value": "Public domain", "source": "mediawiki-metadata", "hidden": ""},
                                    "Artist": {"value": "NASA", "source": "mediawiki-metadata"},
                                },
                            },
                        ],
                    },
                }
            }
        }
    )

    result = _get_commons_image_with_cleared_cache("Kepler-22b exoplanet", "Kepler-22b")

    assert result["data"]["title"] == "Kepler22b pd"


@patch("app.api.commons.requests.get")
def test_non_image_extensions_skipped(mock_get):
    mock_get.return_value = _commons_response(
        {
            "query": {
                "pages": {
                    "1": {
                        "pageid": 1,
                        "ns": 6,
                        "title": "File:Kepler22b.pdf",
                        "index": 1,
                        "imagerepository": "local",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/wikipedia/commons/0/00/Kepler22b.pdf",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Kepler22b.pdf",
                                "extmetadata": {
                                    "Copyrighted": {"value": "False", "source": "mediawiki-metadata", "hidden": ""},
                                    "LicenseShortName": {"value": "Public domain", "source": "mediawiki-metadata", "hidden": ""},
                                },
                            },
                        ],
                    }
                }
            }
        }
    )

    result = _get_commons_image_with_cleared_cache("Kepler-22b exoplanet", "Kepler-22b")

    assert result["ok"] is True
    assert result["data"] is None


@patch("app.api.commons.requests.get")
def test_title_must_mention_the_subject(mock_get):
    """An unrelated public-domain file should not match."""
    mock_get.return_value = _commons_response(
        {
            "query": {
                "pages": {
                    "1": {
                        "pageid": 1,
                        "ns": 6,
                        "title": "File:Random_Space_Art.jpg",
                        "index": 1,
                        "imagerepository": "local",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/wikipedia/commons/0/00/Random.jpg",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Random.jpg",
                                "extmetadata": {
                                    "Copyrighted": {"value": "False", "source": "mediawiki-metadata", "hidden": ""},
                                    "LicenseShortName": {"value": "Public domain", "source": "mediawiki-metadata", "hidden": ""},
                                },
                            },
                        ],
                    }
                }
            }
        }
    )

    result = _get_commons_image_with_cleared_cache("Kepler-22b exoplanet", "Kepler-22b")

    assert result["ok"] is True
    assert result["data"] is None


@patch("app.api.commons.requests.get")
def test_http_error_returns_fail_envelope(mock_get):
    mock_get.side_effect = Exception("HTTP 500")

    result = _get_commons_image_with_cleared_cache("Kepler-22b exoplanet", "Kepler-22b")

    assert result["ok"] is False
    assert result["data"] is None
    assert "HTTP 500" in result["error"]


@patch("app.api.commons.requests.get")
def test_transport_error_returns_fail_envelope(mock_get):
    from requests.exceptions import ConnectionError, Timeout

    for exc in [Timeout("timed out"), ConnectionError("refused")]:
        mock_get.side_effect = exc
        result = _get_commons_image_with_cleared_cache("Kepler-22b exoplanet", "Kepler-22b")
        assert result["ok"] is False
        assert result["data"] is None
        assert result["error"]


@patch("app.api.commons.requests.get")
def test_search_is_memoized(mock_get):
    mock_get.return_value = _commons_response(
        {
            "query": {
                "pages": {
                    "1": {
                        "pageid": 1,
                        "ns": 6,
                        "title": "File:TRAPPIST-1e_Artist%27s_Impression.png",
                        "index": 1,
                        "imagerepository": "local",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/wikipedia/commons/5/5f/TRAPPIST-1e_Artist%27s_Impression.png",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:TRAPPIST-1e_Artist%27s_Impression.png",
                                "extmetadata": {
                                    "Copyrighted": {"value": "False", "source": "mediawiki-metadata", "hidden": ""},
                                    "LicenseShortName": {"value": "Public domain", "source": "mediawiki-metadata", "hidden": ""},
                                    "Artist": {"value": "NASA/JPL-Caltech", "source": "mediawiki-metadata"},
                                },
                            },
                        ],
                    },
                }
            }
        }
    )

    app = _app()
    with app.app_context():
        from app.cache import cache

        cache.clear()
        first = search_commons_image("TRAPPIST-1e exoplanet", "TRAPPIST-1e")
        second = search_commons_image("TRAPPIST-1e exoplanet", "TRAPPIST-1e")

    assert mock_get.call_count == 1
    assert first["data"]["url"] == second["data"]["url"]
