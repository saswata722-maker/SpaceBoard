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
│   │   ├── apod.py                # Astronomy Picture of the Day API calls (+ image-library failover)
│   │   ├── exoplanets.py          # Exoplanet Archive API calls
│   │   ├── images.py              # NASA Image Library client (APOD failover + shared search helpers)
│   │   ├── imagery.py             # Per-body image lookup for detail pages
│   │   ├── commons.py             # Wikimedia Commons image search (exoplanet fallback)
│   │   ├── spacefacts.py          # Daily space facts from Wikipedia On This Day / Open Notify / NASA Fireball
│   │   └── solar_system.py        # Solar System OpenData API calls
│   │
│   ├── routes/                    # Flask routes/blueprints, one per section
│   │   ├── __init__.py
│   │   ├── home.py                # / - Home landing view (APOD preview)
│   │   ├── asteroids.py           # /asteroids/ - Asteroids table & /asteroids/<id> detail
│   │   ├── planets.py             # /planets/ - Solar system planets & exoplanets
│   │   └── sky.py                 # /sky/ - Sky map & /sky/api/planet-positions
│   │
│   ├── templates/                 # Jinja2 HTML templates
│   │   ├── base.html              # Shared layout + Tailwind CDN script tag
│   │   ├── home.html
│   │   ├── asteroids.html
│   │   ├── asteroid_detail.html   # Single asteroid view
│   │   ├── planets.html
│   │   ├── planet_detail.html     # Single planet view
│   │   ├── exoplanet_detail.html  # Single exoplanet view
│   │   ├── sky.html               # Canvas planisphere container & control aside
│   │   ├── 404.html
│   │   └── 500.html
│   │
│   ├── static/                    # CSS, JS, static datasets, images (Tailwind via CDN)
│   │   ├── css/
│   │   │   └── style.css          # Glassmorphism design system, animations, night mode
│   │   ├── data/
│   │   │   ├── constellations.json# Segment lines for major constellations
│   │   │   └── stars.json         # Hipparcos star catalog (mag <= 4.5)
│   │   ├── js/
│   │   │   ├── main.js            # Global navbar toggling
│   │   │   ├── planet-tonight.js  # Live horizon calculations on planet cards
│   │   │   └── sky.js             # 2D canvas renderer & ephemeris interaction
│   │   └── images/
│   │
├── tests/                         # Unit & integration test suites
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures
│   ├── test_neows.py
│   ├── test_apod.py
│   ├── test_exoplanets.py
│   ├── test_solar_system.py
│   ├── test_routes.py
│   ├── test_sky.py                # Planisphere route & planet-positions API tests
│   ├── test_constellations.py     # Constellation data geometry & DOM contract tests
│   ├── test_images.py             # NASA Image Library client tests
│   ├── test_imagery.py            # Body-image lookup tests
│   ├── test_commons.py            # Wikimedia Commons search tests
│   ├── test_config.py             # Configuration & secrets handling tests
│   ├── test_spacefacts.py         # Daily space facts fallback chain tests
│   └── test_js_syntax.py          # JavaScript syntax validation tests
│
├── .env.example                   # Template for required environment variables
├── .gitignore
├── config.py                      # App configuration (API keys, cache settings)
├── requirements.txt               # Runtime dependencies (incl. gunicorn)
├── requirements-dev.txt           # Test dependencies (pytest)
├── run.py                         # Local development server entry point
├── wsgi.py                        # Production WSGI entry point (gunicorn wsgi:app)
├── Dockerfile                     # Container image definition
├── docker-entrypoint.sh           # Container entrypoint (PORT expansion, exec gunicorn)
├── docker-compose.yml             # Local container orchestration
├── render.yaml                    # Render deployment blueprint
├── LICENSE                        # MIT license text
├── README.md
├── REQUIREMENTS.md               # Interface, visual & data-integrity requirements (IR-01..IR-04)
└── PROJECT_STRUCTURE.md
```

## Folder Notes

- **`app/api/`** — keeps all `requests` calls to NASA, Wikimedia, and OpenData endpoints isolated here. Each function catches failures (timeouts, rate limits, bad responses) and returns a consistent fallback shape rather than raising, so routes/templates can show a friendly "unavailable" state. Modules include NeoWs (`neows.py`), APOD with Image Library failover (`apod.py`, `images.py`), Exoplanet Archive (`exoplanets.py`), Solar System OpenData (`solar_system.py`), per-body imagery (`imagery.py`), Wikimedia Commons search (`commons.py`), and daily space facts (`spacefacts.py`).
- **`app/cache.py`** — configures Flask-Caching (SimpleCache backend, ~1 hour default TTL). Route handlers or `app/api/` functions are decorated with `@cache.cached(...)` or `@cache.memoize(...)` to avoid re-hitting NASA's API for the same data within the TTL window.
- **`app/routes/`** — one Flask Blueprint per section (`home`, `asteroids`, `planets`, `sky`), registered in `app/__init__.py`.
- **`app/templates/`** — Jinja2 templates. `base.html` holds shared layout (nav/footer) and loads Tailwind via a CDN `<script>` tag — no Node/npm build step required. Other pages extend it.
- **`app/static/css/`** — the glassmorphism design system; loaded once by `base.html` (and `sky.html`) to keep component markup readable.
- **`app/static/data/`** — astronomical datasets (`stars.json` with Hipparcos catalog data and `constellations.json` with segment geometry).
- **`app/static/js/`** — vanilla JS modules (`main.js`, `sky.js`, `planet-tonight.js`) consuming `astronomy-engine` directly in browser.
- **`config.py`** — loads environment variables (NASA API key, debug mode, cache settings) using `python-dotenv`, treating template placeholders as unset so documented fallbacks still apply.
- **`wsgi.py`** — production WSGI entry point used by gunicorn; kept separate from `run.py` so the Werkzeug debugger can never be enabled by a production start command.
- **`tests/`** — comprehensive unit and integration tests covering routes, API clients (NeoWs, APOD, Exoplanets, Solar System, NASA Image Library, Wikimedia Commons, Space Facts), caching, celestial calculations, template/JS contracts, configuration hygiene, and JavaScript syntax validation.

## Deployment Notes

- **WSGI entry point**: `wsgi:app` (gunicorn / uWSGI / mod_wsgi).
- **Local dev**: `python run.py` — add `FLASK_DEBUG=1` to `.env` to enable the debugger explicitly.
- **Container**: `Dockerfile` + `docker-entrypoint.sh` build a non-root image; the entrypoint expands `$PORT` and `exec`s gunicorn so the master process is PID 1 and receives `SIGTERM` for graceful shutdown.
- **Caching caveat**: `SimpleCache` is per-process in-memory. Fine for a single instance; switch to `FileSystemCache` or Redis when scaling past one process.

## Naming Conventions

- Modules/files: `snake_case.py`
- Flask Blueprints: `snake_case`, e.g. `asteroids_bp`, `sky_bp`
- Functions: `snake_case`
- Classes: `PascalCase`

## Deferred / Future Enhancements

- **PWA support** (Web App Manifest + Service Worker for offline caching) — intentionally left out of v1 to keep scope manageable for a personal project. Can be added later as `static/manifest.json` and `static/js/sw.js` without restructuring the app.

