import re
from urllib.parse import unquote

import requests

from app.cache import cache

COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"

REQUEST_TIMEOUT = 10

USER_AGENT = "SpaceBoard/1.0 (educational project; contact via the repository)"

# Commons holds every kind of file; only these render in a browser.
WEB_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".gif")

_TAG_RE = re.compile(r"<[^>]+>")
_UTM_RE = re.compile(r"[?&]utm_[^&]+")


def _ok(data):
    """Wrap a successful API response."""
    return {"ok": True, "data": data, "error": None}


def _fail(message):
    """Wrap a failed API response with a human-readable message."""
    return {"ok": False, "data": None, "error": message}


@cache.memoize(timeout=3600)
def _fetch_commons_cached(query):
    """Search Commons and return raw JSON; raise on failure."""
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(
        COMMONS_API_URL,
        params={
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": 10,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata",
            "format": "json",
        },
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _compact(text):
    return re.sub(r"[^a-z0-9]", "", text.lower()) if isinstance(text, str) else ""


def _is_web_image(url):
    return bool(url) and url.lower().split("?")[0].endswith(WEB_IMAGE_SUFFIXES)


def _is_free_to_reuse(metadata):
    """Only public-domain / CC0 art: Commons also holds CC BY-SA illustrations,
    which are not appropriate for a hero image."""
    extmetadata = metadata.get("extmetadata") if isinstance(metadata, dict) else None
    if not isinstance(extmetadata, dict):
        return False
    copyrighted = extmetadata.get("Copyrighted", {}).get("value")
    return copyrighted == "False"


def _clean(value):
    """extmetadata fields often carry inline HTML."""
    return _TAG_RE.sub("", value).strip() if isinstance(value, str) else ""


def _display_title(title):
    """A Commons file title as a readable caption.

    Commons names files "File:TRAPPIST-1e_Artist%27s_Impression.png"; the
    caption reads "TRAPPIST-1e Artist's Impression" — the extension and
    namespace are dropped, percent-escapes are decoded, and underscores
    become spaces.
    """
    text = _clean(title)
    text = re.sub(r"\.(jpg|jpeg|png|webp|gif)$", "", text, flags=re.I)
    if text.startswith("File:"):
        text = text[len("File:"):]
    return unquote(text).replace("_", " ")


def _clean_url(url):
    """The API appends campaign tracking to every URL."""
    if not isinstance(url, str):
        return ""
    return _UTM_RE.sub("", url).replace("?&", "?").rstrip("?&")


def _commons_files(payload, designation):
    """Every file that depicts the subject and may be shown, in search order.

    Requires a web-renderable image whose title names the subject (so
    "kepler22b" matches a file called "Kepler22b.png") and that is public
    domain. Search order is relevance order, so the first hit wins.
    """
    pages = payload.get("query", {}).get("pages") if isinstance(payload, dict) else None
    if not isinstance(pages, dict):
        return []

    designation_compact = _compact(designation)
    results = []
    for page in pages.values():
        if not isinstance(page, dict):
            continue
        info = (page.get("imageinfo") or [{}])[0]
        url = _clean_url(info.get("url", ""))
        if not _is_web_image(url):
            continue
        if not _is_free_to_reuse(info):
            continue
        if len(designation_compact) >= 4 and designation_compact not in _compact(
            page.get("title", "")
        ):
            continue
        results.append((page, info, url))

    results.sort(key=lambda entry: entry[0].get("index", 0))
    files = []
    for page, info, url in results:
        extmetadata = info.get("extmetadata") or {}
        files.append(
            {
                "url": url,
                "title": _display_title(page.get("title", "")),
                "credit": _clean(extmetadata.get("Artist", {}).get("value", ""))
                or _clean(extmetadata.get("Credit", {}).get("value", "")),
                "license": _clean(extmetadata.get("LicenseShortName", {}).get("value", "")),
                "file_page_url": _clean_url(info.get("descriptionurl", "")),
                "provider": "Wikimedia Commons",
            }
        )
    return files


def search_commons_image(query, designation):
    """Search Wikimedia Commons for an image naming the subject.

    Args:
        query: The search string (e.g. "TRAPPIST-1e exoplanet").
        designation: The subject as NASA catalogues it (e.g. "TRAPPIST-1e"),
            matched against each file's title.

    Returns:
        dict: {"ok": bool, "data": {"url", "title", "credit", "license",
               "file_page_url", "provider"}|None, "error": str|None}

    ``data`` is None when nothing suitable exists — an empty result is not a
    failure, so callers degrade to their text-only layout.
    """
    try:
        payload = _fetch_commons_cached(query)
    except requests.exceptions.Timeout:
        return _fail("The request to Wikimedia Commons timed out.")
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        return _fail(f"Wikimedia Commons returned an error (HTTP {status}).")
    except requests.exceptions.RequestException as e:
        return _fail(f"Could not reach Wikimedia Commons: {str(e)}")
    except Exception as e:
        return _fail(f"Unexpected error searching Wikimedia Commons: {str(e)}")

    files = _commons_files(payload, designation)
    return _ok(files[0] if files else None)


def search_commons_images(query, designation):
    """Every eligible Commons file for designation, in search order.

    Same envelope and error handling as ``search_commons_image``; ``data`` is
    a list (possibly empty). Callers pick from it — see
    ``imagery.get_body_image``, which rotates a per-day index across the list.
    An empty result is not a failure.
    """
    try:
        payload = _fetch_commons_cached(query)
    except requests.exceptions.Timeout:
        return _fail("The request to Wikimedia Commons timed out.")
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        return _fail(f"Wikimedia Commons returned an error (HTTP {status}).")
    except requests.exceptions.RequestException as e:
        return _fail(f"Could not reach Wikimedia Commons: {str(e)}")
    except Exception as e:
        return _fail(f"Unexpected error searching Wikimedia Commons: {str(e)}")

    return _ok(_commons_files(payload, designation))
