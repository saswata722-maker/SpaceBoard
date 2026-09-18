# Project Structure (Python / Flask)

```
nasa-explorer/
├── app/
│   ├── __init__.py                # Flask app factory + cache init
│   ├── cache.py                    # Flask-Caching configuration (SimpleCache, 1hr TTL)
│   │
│   ├── api/                       # NASA API call functions live here
│   │   ├── __init__.py
│   │   ├── neows.py                 # Asteroid / NeoWs API calls
│   │   ├── apod.py                  # Astronomy Picture of the Day API calls
│   │   ├── exoplanets.py            # Exoplanet Archive API calls
│   │   └── solar_system.py          # Solar System OpenData API calls
│   │
│   ├── routes/                    # Flask routes/blueprints, one per section
│   │   ├── __init__.py
│   │   ├── home.py
│   │   ├── asteroids.py
│   │   ├── planets.py
│   │   └── stars.py
│   │
│   ├── templates/                 # Jinja2 HTML templates
│   │   ├── base.html                # Shared layout + Tailwind CDN script tag
│   │   ├── home.html
│   │   ├── asteroids.html
│   │   ├── planets.html
│   │   └── stars.html
│   │
│   ├── static/                    # JS, images (no bundled CSS needed — Tailwind via CDN)
│   │   ├── js/
│   │   │   └── main.js
│   │   └── images/
│   │
│   └── utils/                     # Helper functions (formatting, date logic, etc.)
│       ├── __init__.py
│       ├── format_date.py
│       └── hazard_color.py
│
├── tests/                         # Unit tests
│   ├── __init__.py
│   ├── test_neows.py
│   ├── test_apod.py
│   └── test_routes.py
│
├── .env.example                   # Template for required environment variables
├── .gitignore
├── config.py                      # App configuration (API keys, settings)
├── requirements.txt                # Flask, requests, Flask-Caching, python-dotenv
├── run.py                          # Entry point to start the Flask app
├── README.md
└── PROJECT_STRUCTURE.md
```

## Folder Notes

- **`app/api/`** — keep all `requests` calls to NASA endpoints isolated here. Each function should catch failures (timeouts, rate limits, bad responses) and return a consistent fallback shape rather than raising, so routes/templates can show a friendly "unavailable" state.
- **`app/cache.py`** — configures Flask-Caching (SimpleCache backend, ~1 hour TTL). Route handlers or `app/api/` functions can be decorated with `@cache.cached(...)` or `@cache.memoize(...)` to avoid re-hitting NASA's API for the same data within the TTL window. This matters because NASA's free API key has a rate limit.
- **`app/routes/`** — one Flask Blueprint per section (home, asteroids, planets, stars), registered in `app/__init__.py`.
- **`app/templates/`** — Jinja2 templates. `base.html` holds shared layout (nav/footer) and loads Tailwind via a CDN `<script>` tag — no Node/npm build step required. Other pages extend it.
- **`app/static/`** — JS and images only. No compiled CSS folder needed since Tailwind loads from CDN.
- **`app/utils/`** — small pure functions (date formatting, hazard-level color mapping, etc.) with no side effects.
- **`config.py`** — loads environment variables (NASA API key, debug mode, etc.) using `python-dotenv`.
- **`tests/`** — mirrors `app/` structure for unit tests.

## Naming Conventions

- Modules/files: `snake_case.py`
- Flask Blueprints: `snake_case`, e.g. `asteroids_bp`
- Functions: `snake_case`
- Classes: `PascalCase`

## Deferred / Future Enhancements

- **PWA support** (Web App Manifest + Service Worker for offline caching) — intentionally left out of v1 to keep scope manageable for a personal project. Can be added later as `static/manifest.json` and `static/js/sw.js` without restructuring the app.
