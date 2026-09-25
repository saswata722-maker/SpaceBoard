# Project Structure (Python / Flask)

```
SpaceBoard/
├── app/
│   ├── __init__.py                # Flask app factory + cache init & error handlers
│   ├── cache.py                   # Flask-Caching configuration (SimpleCache, 1hr TTL)
│   │
│   ├── api/                       # External API call functions live here
│   │   ├── __init__.py
│   │   ├── neows.py               # Asteroid / NeoWs API calls
│   │   ├── apod.py                # Astronomy Picture of the Day API calls
│   │   ├── exoplanets.py          # Exoplanet Archive API calls
│   │   └── solar_system.py        # Solar System OpenData API calls
│   │
│   ├── routes/                    # Flask routes/blueprints, one per section
│   │   ├── __init__.py
│   │   ├── home.py                # / - Home landing view
│   │   ├── asteroids.py           # /asteroids/ - Asteroids table view
│   │   ├── planets.py             # /planets/ - Solar system planets & exoplanets
│   │   ├── stars.py               # /stars/ - APOD stars archive & gallery
│   │   └── sky.py                 # /sky/ - Sky map & /sky/api/planet-positions
│   │
│   ├── templates/                 # Jinja2 HTML templates
│   │   ├── base.html              # Shared layout + Tailwind CDN script tag
│   │   ├── home.html
│   │   ├── asteroids.html
│   │   ├── planets.html
│   │   ├── stars.html
│   │   ├── sky.html               # Canvas planisphere container & control aside
│   │   ├── 404.html
│   │   └── 500.html
│   │
│   ├── static/                    # JS, static datasets, images (Tailwind via CDN)
│   │   ├── data/
│   │   │   ├── constellations.json# Segment lines for major constellations
│   │   │   └── stars.json         # Hipparcos star catalog (mag <= 4.5)
│   │   ├── js/
│   │   │   ├── main.js            # Global navbar toggling
│   │   │   ├── planet-tonight.js  # Live horizon calculations on planet cards
│   │   │   └── sky.js             # 2D canvas renderer & ephemeris interaction
│   │   └── images/
│   │
│   └── utils/                     # Helper functions (formatting, date logic, etc.)
│       ├── __init__.py
│       ├── format_date.py
│       └── hazard_color.py
│
├── tests/                         # Unit & integration test suites
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures
│   ├── test_neows.py
│   ├── test_apod.py
│   ├── test_exoplanets.py
│   ├── test_solar_system.py
│   ├── test_routes.py
│   ├── test_sky.py                # Planisphere route & planet-positions API tests
│   └── test_constellations.py     # Constellation data geometry & DOM contract tests
│
├── .env.example                   # Template for required environment variables
├── .gitignore
├── config.py                      # App configuration (API keys, cache settings)
├── requirements.txt               # Flask, requests, Flask-Caching, python-dotenv, pytest
├── run.py                         # Entry point to start the Flask app
├── README.md
└── PROJECT_STRUCTURE.md
```

## Folder Notes

- **`app/api/`** — keeps all `requests` calls to NASA and OpenData endpoints isolated here. Each function catches failures (timeouts, rate limits, bad responses) and returns a consistent fallback shape rather than raising, so routes/templates can show a friendly "unavailable" state.
- **`app/cache.py`** — configures Flask-Caching (SimpleCache backend, ~1 hour default TTL). Route handlers or `app/api/` functions are decorated with `@cache.cached(...)` or `@cache.memoize(...)` to avoid re-hitting NASA's API for the same data within the TTL window.
- **`app/routes/`** — one Flask Blueprint per section (`home`, `asteroids`, `planets`, `stars`, `sky`), registered in `app/__init__.py`.
- **`app/templates/`** — Jinja2 templates. `base.html` holds shared layout (nav/footer) and loads Tailwind via a CDN `<script>` tag — no Node/npm build step required. Other pages extend it.
- **`app/static/data/`** — astronomical datasets (`stars.json` with Hipparcos catalog data and `constellations.json` with segment geometry).
- **`app/static/js/`** — vanilla JS modules (`main.js`, `sky.js`, `planet-tonight.js`) consuming `astronomy-engine` directly in browser.
- **`app/utils/`** — small pure functions (date formatting, hazard-level color mapping, etc.) with no side effects.
- **`config.py`** — loads environment variables (NASA API key, debug mode, cache settings) using `python-dotenv`.
- **`tests/`** — comprehensive unit and integration tests covering routes, API clients, caching, celestial calculations, and template/JS contracts.

## Naming Conventions

- Modules/files: `snake_case.py`
- Flask Blueprints: `snake_case`, e.g. `asteroids_bp`, `sky_bp`
- Functions: `snake_case`
- Classes: `PascalCase`

## Deferred / Future Enhancements

- **PWA support** (Web App Manifest + Service Worker for offline caching) — intentionally left out of v1 to keep scope manageable for a personal project. Can be added later as `static/manifest.json` and `static/js/sw.js` without restructuring the app.

