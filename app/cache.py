from flask_caching import Cache

# SimpleCache backend — in-memory, no external dependencies.
# Decorating API functions with @cache.memoize() keeps repeated
# requests within the TTL window from hitting NASA's rate-limited endpoints.
cache = Cache()
