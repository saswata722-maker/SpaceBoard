"""Credential-handling checks: .env is ignored, read correctly, and never
reaches the browser.

These exist because a real defect shipped here: `os.getenv("NASA_API_KEY",
"DEMO_KEY")` returns "" when the variable exists but is empty — which is exactly
what a copied-but-unfilled .env produces — so the documented fallback was
silently bypassed and NASA received `api_key=`.
"""
import os
from unittest.mock import patch

import pytest

from config import _env

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GITIGNORE = os.path.join(BASE, ".gitignore")
ENV_EXAMPLE = os.path.join(BASE, ".env.example")


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


@pytest.fixture
def client():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# --------------------------------------------------------------------------
# .env hygiene
# --------------------------------------------------------------------------

def test_env_is_gitignored():
    """The real .env holds credentials and must never be committed."""
    lines = {line.strip() for line in _read(GITIGNORE).splitlines()}
    assert ".env" in lines
    assert ".env.*" in lines


def test_env_example_is_not_gitignored():
    """The blueprint is the one env file that must stay committed."""
    lines = {line.strip() for line in _read(GITIGNORE).splitlines()}
    assert "!.env.example" in lines


def test_env_example_documents_every_secret_the_code_reads():
    text = _read(ENV_EXAMPLE)
    for name in ("NASA_API_KEY", "SOLAR_SYSTEM_API_KEY", "SECRET_KEY"):
        assert name in text, f"{name} missing from .env.example blueprint"


# --------------------------------------------------------------------------
# Fallback semantics
# --------------------------------------------------------------------------

def test_blank_env_value_still_falls_back(monkeypatch):
    """An empty variable must not defeat the DEMO_KEY fallback."""
    monkeypatch.setenv("NASA_API_KEY", "")
    assert _env("NASA_API_KEY", "DEMO_KEY") == "DEMO_KEY"


def test_whitespace_only_env_value_still_falls_back(monkeypatch):
    monkeypatch.setenv("NASA_API_KEY", "   ")
    assert _env("NASA_API_KEY", "DEMO_KEY") == "DEMO_KEY"


def test_placeholder_from_the_template_falls_back(monkeypatch):
    """Shipping .env.example's placeholder upstream would send a fake key."""
    monkeypatch.setenv("NASA_API_KEY", "your_nasa_api_key_here")
    assert _env("NASA_API_KEY", "DEMO_KEY") == "DEMO_KEY"


def test_real_key_is_used_verbatim(monkeypatch):
    monkeypatch.setenv("NASA_API_KEY", "abcdef1234567890")
    assert _env("NASA_API_KEY", "DEMO_KEY") == "abcdef1234567890"


def test_missing_env_value_uses_default(monkeypatch):
    monkeypatch.delenv("SOLAR_SYSTEM_API_KEY", raising=False)
    assert _env("SOLAR_SYSTEM_API_KEY") == ""


# --------------------------------------------------------------------------
# The solar-system bearer token comes from config, not import time
# --------------------------------------------------------------------------

@patch("app.api.solar_system.requests.get")
def test_solar_headers_use_configured_key(mock_get):
    from app import create_app
    from app.api.solar_system import get_bodies

    mock_response = mock_get.return_value
    mock_response.json.return_value = {"bodies": []}
    mock_response.raise_for_status.return_value = None

    app = create_app()
    app.config["SOLAR_SYSTEM_API_KEY"] = "test-bearer-token"
    with app.app_context():
        get_bodies()

    assert mock_get.call_args.kwargs["headers"] == {
        "Authorization": "Bearer test-bearer-token"
    }


@patch("app.api.solar_system.requests.get")
def test_solar_headers_empty_when_unconfigured(mock_get):
    from app import create_app
    from app.api.solar_system import get_bodies

    mock_response = mock_get.return_value
    mock_response.json.return_value = {"bodies": []}
    mock_response.raise_for_status.return_value = None

    app = create_app()
    app.config["SOLAR_SYSTEM_API_KEY"] = ""
    with app.app_context():
        get_bodies()

    assert mock_get.call_args.kwargs["headers"] == {}


# --------------------------------------------------------------------------
# Nothing reaches the browser
# --------------------------------------------------------------------------

@patch("app.routes.home.get_apod")
def test_secrets_never_render_into_html(mock_get_apod, client):
    """Sentinels stand in for real credentials; none may appear in any page."""
    sentinels = {
        "NASA_API_KEY": "SENTINEL-NASA-KEY",
        "SOLAR_SYSTEM_API_KEY": "SENTINEL-SOLAR-KEY",
        "SECRET_KEY": "SENTINEL-SECRET-KEY",
    }
    for name, value in sentinels.items():
        client.application.config[name] = value

    mock_get_apod.return_value = {"ok": True, "data": None, "error": None}

    for path in ("/", "/sky/"):
        body = client.get(path).data
        for name, value in sentinels.items():
            assert value.encode() not in body, f"{name} leaked into {path}"


def test_frontend_assets_contain_no_credentials(client):
    """The browser only ever talks to our own endpoints — no key, no bearer."""
    for path in ("/static/js/sky.js", "/static/js/planet-tonight.js",
                 "/static/js/main.js"):
        body = client.get(path).get_data(as_text=True).lower()
        for needle in ("api_key", "apikey", "bearer", "secret", "token="):
            assert needle not in body, f"{needle!r} found in {path}"
