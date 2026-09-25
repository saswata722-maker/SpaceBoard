"""P0-2 checks: constellation line data + sky page/script wiring.

These guard the two failure modes that made the sky map unusable before:
(a) the astronomy-engine CDN URL 404ing / calling functions that do not exist,
(b) sky.js referencing element ids that are not in sky.html.
"""
import json
import os
import re

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
    at least two points per segment, and coordinates inside valid ranges."""
    assert len(constellations) >= 20, "expected the recognisable-constellation set"

    ids = [c["id"] for c in constellations]
    assert len(ids) == len(set(ids)), "duplicate constellation ids"

    point_count = 0
    for c in constellations:
        assert c["name"], c
        assert len(c["lines"]) >= 1, f"{c['id']} has no lines"
        for segment in c["lines"]:
            assert len(segment) >= 2, f"{c['id']} has a degenerate segment"
            for ra, dec in segment:
                assert 0.0 <= ra <= 360.0, f"{c['id']} ra out of range: {ra}"
                assert -90.0 <= dec <= 90.0, f"{c['id']} dec out of range: {dec}"
                point_count += 1

    assert point_count >= 100, "line data looks too sparse to be useful"


def test_expected_constellations_present(constellations):
    ids = {c["id"] for c in constellations}
    for want in ("Ori", "UMa", "Cas", "Cyg", "Lyr", "Aql", "Leo", "Sco",
                 "Tau", "Gem", "Cru", "Peg"):
        assert want in ids, f"missing recognisable constellation {want}"


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
