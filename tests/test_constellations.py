"""P0-2 checks: constellation line data + sky page/script wiring.

These guard the two failure modes that made the sky map unusable before:
(a) the astronomy-engine CDN URL 404ing / calling functions that do not exist,
(b) sky.js referencing element ids that are not in sky.html.
"""
import json
import os
import re
from collections import Counter

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAR_PATH = os.path.join(BASE, "app", "static", "data", "stars.json")
CONST_PATH = os.path.join(BASE, "app", "static", "data", "constellations.json")
SKY_JS = os.path.join(BASE, "app", "static", "js", "sky.js")


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


@pytest.fixture(scope="module")
def constellations():
    with open(CONST_PATH, encoding="utf-8") as handle:
        return json.load(handle)["constellations"]


@pytest.fixture(scope="module")
def sky_js():
    return _read(SKY_JS)


@pytest.fixture(scope="module")
def sky_html():
    return _read(os.path.join(BASE, "app", "templates", "sky.html"))


def test_constellation_file_is_well_formed(constellations):
    """Every constellation has usable geometry: unique id, at least one segment,
    at least two points per segment, coordinates inside valid ranges, and an
    explicit label flag (the file now carries all 88 IAU constellations)."""
    assert len(constellations) >= 88, "expected the full IAU constellation set"

    ids = [c["id"] for c in constellations]
    assert len(ids) == len(set(ids)), "duplicate constellation ids"

    point_count = 0
    labelled = 0
    for c in constellations:
        assert c["name"], c
        assert isinstance(c["label"], bool), f"{c['id']} missing label flag"
        labelled += c["label"]
        assert len(c["lines"]) >= 1, f"{c['id']} has no lines"
        for segment in c["lines"]:
            assert len(segment) >= 2, f"{c['id']} has a degenerate segment"
            for ra, dec in segment:
                assert 0.0 <= ra <= 360.0, f"{c['id']} ra out of range: {ra}"
                assert -90.0 <= dec <= 90.0, f"{c['id']} dec out of range: {dec}"
                point_count += 1

    assert point_count >= 500, "line data looks too sparse to be useful"
    # Only recognisable figures are named on the canvas; labelling all 89 would
    # overlap into unreadable noise.
    assert 20 <= labelled <= 30, f"{labelled} labels - expected only the recognisable subset"


def test_expected_constellations_present(constellations):
    ids = {c["id"] for c in constellations}
    for want in ("Ori", "UMa", "Cas", "Cyg", "Lyr", "Aql", "Leo", "Sco",
                 "Tau", "Gem", "Cru", "Peg"):
        assert want in ids, f"missing recognisable constellation {want}"


def test_only_recognisable_constellations_are_labelled(constellations):
    """All 89 draw lines, but only the familiar figures are named — a viewer
    must not have to hunt through 89 overlapping labels."""
    by_id = {c["id"]: c for c in constellations}

    # recognisable ones must carry a name
    for want in ("Ori", "UMa", "Cas", "Cyg", "Lyr", "Leo", "Sco", "Tau"):
        assert by_id[want]["label"] is True, f"{want} should be labelled"

    # obscure figures must stay unnamed
    for obscure in ("Cae", "Ant", "Nor", "Vul", "Col", "Phe"):
        assert obscure in by_id, f"missing {obscure}"
        assert by_id[obscure]["label"] is False, f"{obscure} should not be labelled"

    # and sky.js honours the flag
    sky_js = _read(SKY_JS)
    assert "if (constellation.label === false) continue;" in sky_js


def test_line_data_does_not_collide_with_star_catalog(constellations):
    """Line points come from the same celestial sphere as the star catalog, so
    they must sit in roughly the same region - catches a unit mix-up (hours vs
    degrees) in the generator."""
    with open(STAR_PATH, encoding="utf-8") as handle:
        stars = json.load(handle)
    assert stars, "star catalog empty"

    decs = [c["lines"][0][0][1] for c in constellations]
    assert all(-90.0 <= d <= 90.0 for d in decs)


def test_sky_js_uses_only_verified_astronomy_apis(sky_js):
    """astronomy-engine has no Epoch/Epicycle constructors and no
    JulianDate.fromDate - calling them threw, which killed the planet layer."""
    for broken in ("Astronomy.Epoch", "Astronomy.Epicycle",
                   "JulianDate.fromDate", "Astronomy.GMST"):
        assert broken not in sky_js, f"{broken} does not exist in astronomy-engine"

    for required in ("Astronomy.Equator(", "Astronomy.Horizon(",
                     "Astronomy.Constellation(", "Astronomy.MakeTime(",
                     "Astronomy.SiderealTime(", "Astronomy.Observer"):
        assert required in sky_js, f"expected {required} in sky.js"


def test_sky_js_element_ids_exist_in_sky_html(sky_js, sky_html):
    """getElementById targets that do not resolve leave the map half-wired."""
    wanted = set(re.findall(r"getElementById\('([^']+)'\)", sky_js))
    assert wanted, "no element references found"

    missing = sorted(i for i in wanted if 'id="%s"' % i not in sky_html)
    assert not missing, f"ids referenced by sky.js but missing from sky.html: {missing}"


def test_sky_html_loads_loadable_engine_url(sky_html):
    """Regression guard: the npm package has no dist/ directory and 2.1.10 was
    never published, so the old script tag 404'd and the sky map had no engine."""
    assert "astronomy-engine@" in sky_html
    assert "/dist/" not in sky_html
    match = re.search(r"astronomy-engine@(\d+\.\d+\.\d+)/([\w.]+)\.js", sky_html)
    assert match, "engine script URL must pin a version and a real file name"
    assert match.group(2) == "astronomy.browser.min"


def test_sky_js_loads_constellation_and_star_data(sky_js):
    assert "/static/data/constellations.json" in sky_js
    assert "/static/data/stars.json" in sky_js
    assert "show-constellations" in sky_js


def test_sky_html_has_constellation_toggle(sky_html):
    assert 'id="show-constellations"' in sky_html
    assert "Constellation lines" in sky_html


# ---------------------------------------------------------------------------
# Time animation controls (Play / Pause / speed / Now)
# ---------------------------------------------------------------------------

ANIMATION_IDS = ("anim-play-btn", "anim-play-icon", "anim-play-text",
                 "anim-speed", "time-now-btn")


def test_sky_html_has_animation_controls(sky_html):
    """Play/Pause, a speed selector and a Now reset must exist in the markup."""
    for element_id in ANIMATION_IDS:
        assert 'id="%s"' % element_id in sky_html, f"missing #{element_id}"
    # speed presets: 60x, 300x, 3600x (default), 86400x
    for value in ("60", "300", "3600", "86400"):
        assert 'value="%s"' % value in sky_html, f"missing speed {value}x"
    assert "selected" in sky_html.split('id="anim-speed"')[1][:400]


def test_sky_js_wires_animation_controls(sky_js):
    """sky.js must bind every control and drive a requestAnimationFrame loop."""
    for element_id in ANIMATION_IDS:
        assert "'%s'" % element_id in sky_js, f"sky.js does not read #{element_id}"

    for required in ("function animStep(", "function startAnimation(",
                     "function stopAnimation(", "requestAnimationFrame(",
                     "performance.now()"):
        assert required in sky_js, f"missing {required}"

    # start/stop are idempotent and toggle the label, not just the state flag
    for required in ("state.animating = true", "state.animating = false",
                     "'Pause'", "'Play'"):
        assert required in sky_js


def test_manual_time_edit_pauses_animation(sky_js):
    """Scrubbing the slider or typing a date must stop playback, otherwise the
    next animation frame overwrites the user's chosen time."""
    assert sky_js.count("stopAnimation();") >= 3, (
        "expected stopAnimation() in the play toggle, the slider handler and "
        "the date-time handler"
    )


def test_animation_step_updates_inputs(sky_js):
    """Each frame must write the simulated clock back into both inputs so the
    date-time picker and the scrub slider stay in sync with the canvas."""
    step_body = sky_js.split("function animStep(")[1].split("if (animPlayBtn)")[0]
    assert "obsTimeInput.value = toLocalInput(" in step_body
    assert "timeSlider.value" in step_body
    # guards against tab-freeze jumps
    assert "dtSec > 0.2" in step_body


def test_sky_js_draws_constellation_labels(sky_js):
    """Lines alone do not tell you what you are looking at; the map also needs
    to name the constellation near each stick figure."""
    assert "drawConstellationLabels" in sky_js
    assert "constellationLabelPoint" in sky_js
    assert "drawStars(size.w, size.h)" in sky_js


def test_star_catalog_has_no_duplicate_positions():
    """The catalog shipped with 36 duplicate (ra, dec) pairs, so those stars
    were drawn twice (too bright) and both copies were clickable."""
    with open(STAR_PATH, encoding="utf-8") as handle:
        stars = json.load(handle)

    keys = [(star["ra"], star["dec"]) for star in stars]
    duplicates = [key for key, count in Counter(keys).items() if count > 1]
    assert not duplicates, f"duplicate star positions: {duplicates[:5]}"


def test_star_catalog_named_stars_are_unique():
    """Dedupe must keep every named star — they are what the labels and hover
    tooltips show — without leaving a name on two records."""
    with open(STAR_PATH, encoding="utf-8") as handle:
        stars = json.load(handle)

    names = [star["name"] for star in stars if star.get("name")]
    duplicates = [name for name, count in Counter(names).items() if count > 1]
    assert not duplicates, f"duplicate star names: {duplicates}"
    assert len(names) >= 20, "too few named stars survived for useful labels"
