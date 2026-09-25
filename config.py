import os

from dotenv import load_dotenv

load_dotenv()

# A fresh clone copies .env.example, so its placeholder values must be treated
# as "not configured" rather than sent upstream as real credentials.
_PLACEHOLDERS = {"", "your_api_key_here", "your_nasa_api_key_here"}


def _env(name, default=""):
    """Read an environment variable, treating blanks and template placeholders
    as unset so the documented fallbacks still apply.

    `os.getenv(name, default)` returns "" when the variable exists but is empty,
    which would silently bypass the DEMO_KEY fallback.
    """
    value = (os.getenv(name) or "").strip()
    return default if value in _PLACEHOLDERS else value


class Config:
    """Application configuration loaded from environment variables (.env).

    Falls back to DEMO_KEY for NASA_API_KEY so the app runs immediately
    without a user signing up for a key. DEMO_KEY has a lower rate limit
    (~30 requests/hour vs 1,000/hour for a registered key).

    All three secrets are read here only; nothing is passed to templates, so no
    credential is exposed to the browser.
    """

    NASA_API_KEY = _env("NASA_API_KEY", "DEMO_KEY")
    SOLAR_SYSTEM_API_KEY = _env("SOLAR_SYSTEM_API_KEY")
    SECRET_KEY = _env("SECRET_KEY", "dev-secret-key-change-in-production")

    FLASK_ENV = _env("FLASK_ENV", "development")
    CACHE_TYPE = _env("CACHE_TYPE", "SimpleCache")
    CACHE_DEFAULT_TIMEOUT = int(_env("CACHE_DEFAULT_TIMEOUT", "3600"))

