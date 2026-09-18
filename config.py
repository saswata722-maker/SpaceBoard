import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration loaded from environment variables.

    Falls back to DEMO_KEY for NASA_API_KEY so the app runs immediately
    without a user signing up for a key. DEMO_KEY has a lower rate limit
    (~30 requests/hour vs 1,000/hour for a registered key).
    """

    NASA_API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    CACHE_TYPE = os.getenv("CACHE_TYPE", "SimpleCache")
    CACHE_DEFAULT_TIMEOUT = int(os.getenv("CACHE_DEFAULT_TIMEOUT", 3600))
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
