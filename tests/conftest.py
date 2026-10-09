"""Shared pytest fixtures.

    The Flask-Caching `cache` object is a module-level singleton, and `create_app()`
    is called once per test. Memoized API results therefore survive from one test to
    the next, which makes tests order-dependent. Clearing the cache
    around every test keeps runs deterministic.
    """
import pytest

from app.cache import cache


@pytest.fixture(autouse=True)
def clear_cache_between_tests():
    if getattr(cache, "app", None) is not None:
        cache.clear()
    yield
    if getattr(cache, "app", None) is not None:
        cache.clear()
