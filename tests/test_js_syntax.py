"""Tests for JS syntax errors in static/js/ files.

The original bracket-balance checker missed the missing-comma bug in sky.js.
This module adds a regex-based heuristic that flags adjacent object properties
separated only by a newline (no comma).  It will not catch every possible
variant, but it covers the exact pattern that caused the outage.
"""

import os
import re

import pytest


JS_DIR = os.path.join(
    os.path.dirname(__file__), os.pardir, "app", "static", "js"
)


def _js_files():
    """Yield absolute paths of *.js files under static/js/."""
    for name in sorted(os.listdir(JS_DIR)):
        if name.endswith(".js"):
            yield os.path.join(JS_DIR, name)


# ---------------------------------------------------------------------------
# Heuristic: flag lines where an object property value is immediately
# followed (after optional whitespace/newline) by another property key
# *without* a comma in between.
#
# Pattern explanation (applied to consecutive line pairs):
#   line A ends with a value token (identifier, number, boolean, string,
#          closing bracket/brace/paren) and NO trailing comma
#   line B starts (after optional whitespace) with a property key followed
#          by a colon  →  probable missing comma
# ---------------------------------------------------------------------------

_VALUE_END = re.compile(
    r"[}\])\w\"\'`]"   # last non-whitespace char looks like a value
    r"\s*$"             # possibly trailing spaces, then EOL
)

_PROP_START = re.compile(
    r"^\s+"             # indented
    r"[a-zA-Z_$]"      # starts with an identifier char
    r"[\w$]*"           # rest of the identifier
    r"\s*:"             # followed by a colon → it's a property key
)


def _find_missing_commas(path):
    """Return a list of ``(line_number, line_text)`` tuples for probable
    missing-comma sites between consecutive lines in *path*."""
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    hits = []
    for i in range(len(lines) - 1):
        line_a = lines[i].rstrip("\n\r")
        line_b = lines[i + 1]

        # Strip inline comment if present
        clean_a = re.sub(r"//.*$", "", line_a).rstrip()
        stripped_a = clean_a.strip()

        # Skip blank / comment-only lines
        if not stripped_a or stripped_a.startswith("/*"):
            continue

        # Line A must NOT already end with a comma or opening brace/bracket
        if stripped_a.endswith(",") or stripped_a.endswith("{") or stripped_a.endswith("("):
            continue

        if _VALUE_END.search(clean_a) and _PROP_START.match(line_b):
            hits.append((i + 1, line_a))

    return hits


@pytest.mark.parametrize("path", list(_js_files()), ids=lambda p: os.path.basename(p))
def test_no_missing_commas_in_object_literals(path):
    """Heuristic: consecutive lines that look like object properties without a
    separating comma are flagged.  This catches the exact bug that killed
    /sky/ (``dragY: 0\\nanimating: false``)."""
    hits = _find_missing_commas(path)
    if hits:
        details = "\n".join(f"  line {n}: {text}" for n, text in hits)
        pytest.fail(
            f"Probable missing comma(s) in {os.path.basename(path)}:\n{details}"
        )
