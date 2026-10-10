import re
from datetime import date as _date

from flask import current_app

from app.api.commons import search_commons_images
from app.api.images import search_images

_EPOCH = _date(1970, 1, 1)


def _day_index():
    """Days since the epoch — a stable per-day index for rotation.

    The upstream search payload is date-independent (and cached), so the daily
    change is selection-side: each body rotates through its own eligible
    images by this index, and every body shares the same index on a given day.
    """
    return (_date.today() - _EPOCH).days

# Other solar-system bodies: when a record names one of these *before* it
# names the subject, the record depicts that other body, not ours — e.g.
# "Europa, taken from Voyager 1 to Jupiter" is a picture of Europa. "Moon",
# "Earth", "Sun" and "planet" are deliberately absent because they appear in
# poetic titles ("A Portrait of Planet and Moon: ... Jupiter and Io"), and so
# are mission names that double as bodies ("Juno").
_OTHER_BODIES = frozenset(
    {
        "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune",
        "pluto", "europa", "io", "ganymede", "callisto", "titan",
        "enceladus", "triton", "charon", "ceres", "vesta", "phobos",
        "deimos", "rhea", "dione", "tethys", "mimas", "iapetus", "miranda",
        "ariel", "umbriel", "oberon", "titania", "proteus", "sedna", "eris",
        "makemake", "haumea", "pallas",
    }
)

# Records that are not a depiction of the subject at all: charts, maps, size
# comparisons, event posters, logos, and photographs of events that merely
# share the body's name (NASA's "Mars Celebration" is a photo of a festival
# in the town of Mars, Pennsylvania). These are never an image of the body.
# Substrings are used so variants are caught too ("compared", "compares",
# "comparison"; "stats", "statistics").
NON_IMAGE_MARKERS = (
    "infographic", "graphic", "diagram", "chart", "poster", "logo", "map",
    "celebration", "festival", "compar", "stats", "statistic",
)

# Records that depict the subject but photograph nothing: artist's concepts,
# illustrations, and animations. NASA's authentic visualisations of a body are
# still images *of* it — for most exoplanets they are the only imagery that
# exists — so they are the fallback when no photograph names it.
VISUALISATION_MARKERS = ("artist", "concept", "illustration", "animation")

# Preference order for a record that names the subject: a photograph that
# *leads* with the subject's name (the strongest signal), then any photograph
# that names it, then NASA's authentic visualisation of it — an artist's
# concept is still an image *of* the subject, and for most exoplanets it is
# the only imagery that exists. Only titles are matched: a body name in a
# *description* is usually context ("as seen from Earth..."), and a record
# that describes the subject while picturing something else is worse than no
# image at all.
_SELECTION_PASSES = (
    (False, True),
    (False, False),
    (True, True),
    (True, False),
)
def _subject_stem(name):
    """The identifier NASA catalogues imagery under.

    Exoplanet designations carry a trailing planet letter ("TRAPPIST-1e")
    while the picture is filed under the system ("TRAPPIST-1"), so that
    letter is dropped for matching. Bodies like "Mars" or "Earth" keep their
    full name.
    """
    for pattern in (r"(?<=[\d\-])[a-zA-Z]$", r"\s[a-zA-Z]$"):
        stem = re.sub(pattern, "", name)
        if stem != name and len(stem) >= 3:
            return stem
    return name


def _words(text):
    return re.findall(r"[a-z0-9]+", text.lower()) if isinstance(text, str) else []


def _compact(text):
    return re.sub(r"[^a-z0-9]", "", text.lower()) if isinstance(text, str) else ""


def _mentions(text, stem):
    """Does *text* name the subject?

    Either the stem appears as a word sequence ("TRAPPIST-1" in "TRAPPIST-1
    Planet Lineup"), or — because NASA files exoplanet art without the
    archive's space, "Kepler-22b" for "Kepler-22 b" — the compacted stem
    appears as a substring. Compaction is only trusted for names long enough
    to be unambiguous, so short names keep their word boundaries.
    """
    words = _words(text)
    stem_words = _words(stem)
    if stem_words and words:
        span = len(stem_words)
        if any(words[i:i + span] == stem_words for i in range(len(words) - span + 1)):
            return True

    stem_compact = _compact(stem)
    return len(stem_compact) >= 4 and stem_compact in _compact(text)


def _names_other_body_first(text, stem):
    """Does *text* name a different major body before it names the subject?"""
    stem_words = _words(stem)
    words = _words(text)
    span = len(stem_words)
    for i in range(len(words) - span + 1):
        if words[i:i + span] == stem_words:
            return any(word in _OTHER_BODIES for word in words[:i])
    return False


def _has_marker(metadata, markers):
    text = " ".join(
        part for part in (metadata.get("title"), metadata.get("description"))
        if isinstance(part, str)
    ).lower()
    return any(marker in text for marker in markers)


def _starts_with_subject(text, stem):
    """Does *text* lead with the subject's name?

    "TRAPPIST-1 Planet Lineup" is about TRAPPIST-1; "Measuring the Masses and
    Diameters of the TRAPPIST-1 Planets" merely mentions it, so a leading name
    is preferred when the search order offers both.
    """
    if _words(text)[: len(_words(stem))] == _words(stem):
        return True
    stem_compact = _compact(stem)
    return len(stem_compact) >= 4 and _compact(text).startswith(stem_compact)


def _describes_subject(metadata, stem, allow_visualisation, subject_first):
    """Does this record show *stem*: the title names it (optionally leading
    with it), it is a depiction of the subject, the title is not about a
    different body, and (unless allowed) it is a photograph rather than a
    visualisation?"""
    if _has_marker(metadata, NON_IMAGE_MARKERS):
        return False
    if not allow_visualisation and _has_marker(metadata, VISUALISATION_MARKERS):
        return False
    title = metadata.get("title")
    if not _mentions(title, stem):
        return False
    if subject_first and not _starts_with_subject(title, stem):
        return False
    return not _names_other_body_first(title, stem)


def _normalise(image):
    metadata = image["metadata"]
    return {
        "url": image["href"],
        "title": metadata.get("title"),
        "credit": metadata.get("secondary_creator") or metadata.get("center"),
        "nasa_id": metadata.get("nasa_id"),
        "provider": "NASA Image and Video Library",
    }


def _designation(name):
    """The subject as NASA and Commons catalogue it.

    The Exoplanet Archive spells the planet letter separately ("TRAPPIST-1 e")
    while imagery is filed under the joined form ("TRAPPIST-1e"), so the space
    is dropped for the downstream lookups. "Mars" and other plain names are
    unchanged.
    """
    stripped = re.sub(r"\s+([a-zA-Z])$", "", name)
    return stripped if stripped != name and len(stripped) >= 3 else name


def _sanitize_query(query):
    """Remove special characters that cause API errors.

    Parentheses and other special characters in asteroid names like "(2024 AB)"
    cause 403 errors from the NASA Image and Video Library API.
    """
    return re.sub(r"[\(\)\[\]\{\}]", "", query).strip()


def _nasa_image(stem, body):
    """The NASA library's image of *stem* for today, or None."""
    query = _sanitize_query(f"{stem} planet")
    for allow_visualisation, subject_first in _SELECTION_PASSES:
        result = search_images(
            query,
            accept=lambda metadata, allow=allow_visualisation, first=subject_first: (
                _describes_subject(metadata, stem, allow, first)
            ),
        )
        if not result["ok"]:
            current_app.logger.warning(
                "Body image lookup failed: name=%s error=%s", body, result["error"]
            )
            return None, result["error"]
        images = result["data"]
        if images:
            return _normalise(images[_day_index() % len(images)]), None
    return None, None


def _commons_image(designation, search_term):
    """Commons' image of *designation* for today, or None; never raises."""
    search_term = _sanitize_query(search_term)
    result = search_commons_images(search_term, designation)
    if not result["ok"]:
        current_app.logger.warning(
            "Body image lookup failed: name=%s error=%s", designation, result["error"]
        )
        return None, result["error"]
    files = result["data"]
    if not files:
        return None, None
    data = files[_day_index() % len(files)]
    return {
        "url": data["url"],
        "title": data["title"],
        "credit": data["credit"],
        "license": data["license"],
        "file_page_url": data["file_page_url"],
        "provider": data["provider"],
    }, None


def get_body_image(name, hostname=None):
    """Search for an image of a celestial body, preferring photographs.

    The NASA Image and Video Library is a full-text search, so the top hit for
    a bare name is often a photo of an event, a map, or a neighbouring object.
    The body name is therefore qualified, every hit is scanned, and the record
    chosen is the first one that actually depicts the subject — a photograph
    preferred over a visualisation.

    The chosen image then rotates daily: every eligible record for the body is
    collected and the day's index picks one, so a profile shows a different
    image of the same body each day (a body with a single eligible image stays
    fixed). Rotation is selection-side only — the cached search payload is
    date-independent, and the date is never part of the query.

    NASA has no photographs of exoplanets, only artist concepts of whole
    systems. When nothing depicts the specific planet, the host star is tried
    for a system view, and then Wikimedia Commons for NASA's public-domain
    artist impression of that planet. Each attempt only runs when the previous
    found nothing, and every accepted file names the subject.

    Args:
        name: The subject body's display name (e.g. "Mars", "TRAPPIST-1 e").
        hostname: Optional host star, used to find system-level imagery.

    Returns:
        dict: {"ok": bool, "data": {"url", "title", "credit", "provider",
               ...}|None, "error": str|None}

    An absent image is not an error: when no source has an image of the
    subject, ``data`` is ``None`` and the caller renders the existing text-only
    layout. No generic, stock, or shared hero image is ever substituted for a
    body no source has an image of.
    """
    if not name or not str(name).strip():
        return {"ok": True, "data": None, "error": None}

    body = str(name).strip()
    stem = _subject_stem(body)
    designation = _designation(body)

    image, error = _nasa_image(stem, body)
    if image is not None:
        return {"ok": True, "data": image, "error": None}

    if hostname and str(hostname).strip():
        host = str(hostname).strip()
        image, host_error = _nasa_image(host, host)
        if image is not None:
            return {"ok": True, "data": image, "error": None}
        error = error or host_error

    image, commons_error = _commons_image(
        designation, f"{designation} exoplanet"
    )
    if image is not None:
        return {"ok": True, "data": image, "error": None}
    error = error or commons_error

    if hostname and str(hostname).strip():
        host = str(hostname).strip()
        image, host_commons_error = _commons_image(host, f"{host} exoplanet")
        if image is not None:
            return {"ok": True, "data": image, "error": None}
        error = error or host_commons_error

    return {"ok": True, "data": None, "error": None}
