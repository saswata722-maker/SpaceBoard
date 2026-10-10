import requests

from app.cache import cache

IMAGES_API_URL = "https://images-api.nasa.gov/search"

PROVIDER_NAME = "NASA Image and Video Library"

FALLBACK_QUERY = "astronomy"


def _ok(data):
    """Wrap a successful API response."""
    return {"ok": True, "data": data, "error": None}


def _fail(message):
    """Wrap a failed API response with a human-readable message."""
    return {"ok": False, "data": None, "error": message}


@cache.memoize(timeout=3600)
def _fetch_search_cached(query):
    """Search the library and return raw JSON on success; raise on failure.

    A separate memoized function from the APOD fetch, so secondary responses
    are cached under their own keys and can never mask a primary recovery.
    """
    response = requests.get(
        IMAGES_API_URL,
        params={"q": query, "media_type": "image"},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


_WEB_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".gif")

_RENDITION_PREFERENCE = ("~orig", "~large", "~medium", "~small", "~thumb")


def _href_is_web_image(href):
    """The canonical ``~orig`` file is not always a JPEG — many NASA records
    carry a ``~orig.tif`` that no browser can render — so only
    browser-displayable renditions are eligible.
    """
    return bool(href) and href.lower().split("?")[0].endswith(_WEB_IMAGE_SUFFIXES)


def _pick_rendition(item):
    """Pick the highest-resolution rendition a browser can actually display.

    Preference: the canonical ``~orig`` file when it is a web image, then the
    descending rendition sizes. The rendered element is constrained by CSS,
    so a smaller-but-renderable source is never fetched for display-size
    reasons.
    """
    links = item.get("links")
    if not isinstance(links, list):
        return None

    web_images = [
        link.get("href")
        for link in links
        if isinstance(link, dict)
        and link.get("render") == "image"
        and _href_is_web_image(link.get("href"))
    ]
    if not web_images:
        return None

    canonical = next(
        (
            link.get("href")
            for link in links
            if isinstance(link, dict) and link.get("rel") == "canonical"
        ),
        None,
    )
    if canonical and _href_is_web_image(canonical):
        return canonical

    for marker in _RENDITION_PREFERENCE:
        chosen = next((href for href in web_images if marker in href), None)
        if chosen:
            return chosen
    return web_images[0]


def _search_items(payload):
    """The item list of a library search payload, or an empty list."""
    if not isinstance(payload, dict):
        return []
    collection = payload.get("collection")
    if not isinstance(collection, dict):
        return []
    items = collection.get("items")
    return items if isinstance(items, list) else []


def _item_image(item):
    """Return ``{"metadata": ..., "href": ...}`` for one search item.

    Returns ``None`` when the item is not a dict, its ``data[0]`` is not a
    dict with ``nasa_id``/``title``, or it carries no browser-renderable
    image rendition. Validation and normalisation share this one predicate
    so they cannot drift apart.
    """
    if not isinstance(item, dict):
        return None
    data = item.get("data")
    if not isinstance(data, list) or not data:
        return None
    metadata = data[0]
    if not isinstance(metadata, dict):
        return None
    if not metadata.get("nasa_id") or not metadata.get("title"):
        return None
    href = _pick_rendition(item)
    if not href:
        return None
    return {"metadata": metadata, "href": href}


def _first_image(payload):
    """The payload's first item as an image, or ``None``.

    The home-page failover validates and normalises the first item alone.
    """
    items = _search_items(payload)
    return _item_image(items[0]) if items else None


def _usable_images(payload):
    """Every usable image in the payload, in the API's relevance order."""
    images = []
    for item in _search_items(payload):
        image = _item_image(item)
        if image is not None:
            images.append(image)
    return images


def _validate_search_payload(payload):
    """Structural validation for a library search payload."""
    return _first_image(payload) is not None


def search_first_image(query, accept=None):
    """Envelope around the memoized search; never raises.

    ``data`` carries the first usable image that ``accept(metadata)``
    approves. With ``accept=None`` only the payload's first item is
    considered (the home-page failover validates that item alone); passing a
    predicate scans every item in relevance order, which the body-imagery
    client uses to find an image of the actual subject.

    ``data`` is ``None`` when the search yields nothing usable — an empty
    result is not a failure.
    """
    try:
        payload = _fetch_search_cached(query)
    except requests.exceptions.Timeout:
        return _fail("The request to the NASA Image and Video Library timed out.")
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        return _fail(f"NASA Image and Video Library returned an error (HTTP {status}).")
    except requests.exceptions.RequestException as e:
        return _fail(f"Could not reach the NASA Image and Video Library: {str(e)}")
    except Exception as e:
        return _fail(f"Unexpected error searching the NASA Image and Video Library: {str(e)}")

    if accept is None:
        return _ok(_first_image(payload))

    for image in _usable_images(payload):
        if accept(image["metadata"]):
            return _ok(image)
    return _ok(None)


def search_images(query, accept=None):
    """Every usable image the search offers, in the API's relevance order.

    Same envelope and error handling as ``search_first_image``; ``data`` is a
    list (possibly empty). Callers pick from it — see
    ``imagery.get_body_image``, which rotates a per-day index across the list
    so a body's profile image changes daily. An empty result is not a failure.
    """
    try:
        payload = _fetch_search_cached(query)
    except requests.exceptions.Timeout:
        return _fail("The request to the NASA Image and Video Library timed out.")
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        return _fail(f"NASA Image and Video Library returned an error (HTTP {status}).")
    except requests.exceptions.RequestException as e:
        return _fail(f"Could not reach the NASA Image and Video Library: {str(e)}")
    except Exception as e:
        return _fail(f"Unexpected error searching the NASA Image and Video Library: {str(e)}")

    images = _usable_images(payload)
    if accept is None:
        return _ok(images)
    return _ok([image for image in images if accept(image["metadata"])])


def get_fallback_image():
    """Secondary provider for the home page's media block.

    Searches the library for the pinned featured query and normalises the
    first usable image into the shape the home template already consumes,
    with native attribution and a ``source`` marker so the media is credited
    to the provider that actually supplied it.
    """
    result = search_first_image(FALLBACK_QUERY)
    if not result["ok"] or not result["data"]:
        return result

    metadata = result["data"]["metadata"]
    return _ok(
        {
            "url": result["data"]["href"],
            "media_type": "image",
            "title": metadata.get("title"),
            "date": (metadata.get("date_created") or "")[:10],
            "copyright": metadata.get("secondary_creator") or metadata.get("center"),
            "source": PROVIDER_NAME,
            "nasa_id": metadata.get("nasa_id"),
        }
    )
