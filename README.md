# SpaceBoard 🌌

A modern Flask web app to explore the solar system, exoplanets, near-Earth asteroids, and the night sky using NASA public data APIs, client-side astronomical ephemeris, and an interactive 2D planisphere.

## Overview

SpaceBoard gives astronomy enthusiasts and curious explorers an intuitive interface to browse:
- **Asteroids** — Near-Earth Objects (NEOs) from NASA NeoWs with hazard assessment, estimated diameters, and close-approach velocities/miss distances.
- **Planets & Exoplanets** — Physical characteristics (mass, radius, gravity, moons) for solar system bodies, searchable database of confirmed exoplanets via NASA's Exoplanet Archive, and real-time **"Where to find this planet tonight"** observing data. Each object has a dedicated detail page.
- **Astronomy Picture of the Day (APOD)** — Daily featured space imagery with a date picker on the home page.
- **Sky Map** — Interactive 2D planisphere rendering celestial objects, stars, constellation lines, coordinate grids, and live planetary positions for any location and time on Earth.

Built for demonstration and portfolio use — cleanly structured, thoroughly tested, with defensive error handling and rate-limit caching throughout.

---

## Features

- [x] **Astronomy Picture of the Day (APOD)**: Daily featured space imagery with date picker, metadata, and media fallbacks.
- [x] **Asteroid Tracker (NeoWs)**: Interactive dashboard of NEOs filterable by date range and hazardous classification.
- [x] **Solar System Explorer**: Physical profiles and orbital data for all major planets via the Solar System OpenData API.
- [x] **"Where to Find This Planet Tonight"**: Real-time browser-side ephemeris calculating altitude, azimuth, compass heading, constellation, distance (AU), and rise/set times using your geolocation.
- [x] **Exoplanet Search**: Query confirmed exoplanets by name or host star with tabular orbital and planetary metrics.
- [x] **Interactive 2D Sky Map**:
  - Hipparcos-derived catalog of 1,052 stars down to magnitude 4.5 with labels for major named stars.
  - Constellation stick-figure lines across major constellations with toggle control.
  - IAU constellation boundary detection powered by astronomy-engine.
  - Real-time planet, Sun, and Moon positions rendered dynamically on the celestial sphere.
  - Cardinal direction presets (North, South, East, West, Zenith, Nadir) plus smooth field-of-view zoom (10° to 180°).
  - Time scrubbing controls (date-time picker + 24-hour slider) and location switching (geolocation or custom lat/long).
  - Interactive celestial object inspection with click details card and hover tooltips.
- [x] **Performance & Resiliency**:
  - Server-side caching via Flask-Caching to conserve NASA API rate limits.
  - Graceful fallback states for every external API call (never crashes when upstream services are down).
  - Client-side ephemeris (no external API calls required for sky map or planet positions).
- [x] **Comprehensive Test Suite**: Unit, integration, and contract tests across all routes, API modules, and static datasets.
- [x] **Detail Pages**: Dedicated views for every planet (`/planets/<id>`), exoplanet (`/planets/exoplanet/<name>`), and asteroid (`/asteroids/<id>`).
- [x] **Glassmorphism UI**: A cohesive glass-and-gradient design system in `app/static/css/style.css` — frosted translucent surfaces, blurred backdrops, animated starfield, staggered entrance animations, red "night mode" for preserving dark-adapted eyes, and full `prefers-reduced-motion` support.

---

## Tech Stack

| Layer | Technology | Description |
| :--- | :--- | :--- |
| **Backend** | Python 3.10+, Flask 3.0 | Application framework and modular Blueprint routing |
| **Templating** | Jinja2 | Server-rendered HTML templates with reusable layouts |
| **Styling** | Tailwind CSS (CDN) + custom CSS | Dark-space glassmorphism design system without a Node build step |
| **Caching** | Flask-Caching | In-memory SimpleCache layer for NASA and solar system API endpoints |
| **Astronomical Calculations** | astronomy-engine 2.1 | Fast, client-side ephemeris for real-time positions, constellations, and rise/set times |
| **Client Rendering** | HTML5 Canvas 2D | Custom stereographic/orthographic planisphere projection |
| **Testing** | pytest | Automated test suite covering routes, API adapters, and sky map contracts |
| **Data Sources** | NASA APIs, Le Système Solaire | NeoWs, APOD, NASA Exoplanet Archive, Solar System OpenData API |

---

## Project Structure

```text
SpaceBoard/
├── app/
│   ├── __init__.py                # Flask application factory, blueprint registration & error handlers
│   ├── cache.py                   # Flask-Caching instance (SimpleCache, 1-hour default TTL)
│   │
│   ├── api/                       # External API integration modules
│   │   ├── __init__.py
│   │   ├── apod.py                # NASA Astronomy Picture of the Day API client
│   │   ├── exoplanets.py          # NASA Exoplanet Archive TAP/queries
│   │   ├── neows.py               # NASA NeoWs Near-Earth Object feed client
│   │   └── solar_system.py        # Solar System OpenData API client
│   │
│   ├── routes/                    # Blueprint route controllers
│   │   ├── __init__.py
│   │   ├── asteroids.py           # /asteroids/ - NEO table, filtering & /asteroids/<id> detail
│   │   ├── home.py                # / - Landing page with APOD preview
│   │   ├── planets.py             # /planets/ & detail views /planets/<id>, /planets/exoplanet/<name>
│   │   └── sky.py                 # /sky/ - Sky map & /sky/api/planet-positions endpoint
│   │
│   ├── static/                    # Client-side static assets
│   │   ├── css/
│   │   │   └── style.css          # Glassmorphism design system, animations, night-vision mode
│   │   ├── data/
│   │   │   ├── constellations.json# Curated constellation stick-figure segments (RA/Dec)
│   │   │   └── stars.json         # Hipparcos star catalog (mag <= 4.5, names, coordinates)
│   │   ├── js/
│   │   │   ├── main.js            # Mobile navigation drawer and global UI behaviors
│   │   │   ├── planet-tonight.js  # Live tonight ephemeris computation on planet cards
│   │   │   └── sky.js             # Canvas 2D planisphere renderer, math & user interactions
│   │   └── images/                # Static graphic assets and icons
│   │
│   ├── templates/                 # Jinja2 templates
│   │   ├── 404.html               # Custom 404 error page
│   │   ├── 500.html               # Custom 500 error page
│   │   ├── asteroid_detail.html   # Single asteroid detail view
│   │   ├── asteroids.html         # Asteroid dashboard view
│   │   ├── base.html              # Base layout with navigation and footer
│   │   ├── exoplanet_detail.html  # Single exoplanet detail view
│   │   ├── home.html              # Home landing page
│   │   ├── planet_detail.html     # Single planet detail view
│   │   ├── planets.html           # Planet cards and exoplanet table view
│   │   └── sky.html               # Full-screen interactive sky map view
│   │
├── tests/                         # Pytest test suite
│   ├── __init__.py
│   ├── conftest.py                # Shared pytest fixtures (mock clients, sample data)
│   ├── test_apod.py               # APOD API adapter unit tests
│   ├── test_constellations.py     # Constellation data geometry & JS/HTML contract checks
│   ├── test_exoplanets.py         # Exoplanet API query & error handling tests
│   ├── test_neows.py              # NeoWs API adapter & hazard logic tests
│   ├── test_routes.py             # Flask route responses, status codes & template rendering
│   ├── test_sky.py                # Sky route, /sky/api/planet-positions & caching tests
│   └── test_solar_system.py       # Solar system API adapter & fallback tests
│
├── .env.example                   # Environment configuration template
├── .gitignore                     # Git ignore rules
├── config.py                      # App configuration & environment loader
├── requirements.txt               # Runtime Python dependencies (pinned)
├── requirements-dev.txt           # Test/lint dependencies for local development
├── run.py                         # Local development server entry point
├── wsgi.py                        # Production WSGI entry point (gunicorn / uWSGI)
├── Dockerfile                     # Container image definition
├── docker-compose.yml             # Local container orchestration
├── LICENSE                        # MIT license text
├── README.md                      # Project documentation
└── PROJECT_STRUCTURE.md           # Architectural layout and design guidelines
```

---

## Getting Started

### Prerequisites

- **Python 3.10+**
- A free NASA API key from [api.nasa.gov](https://api.nasa.gov/) *(Optional: SpaceBoard falls back automatically to `DEMO_KEY` if none is configured).*

### Installation

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd SpaceBoard
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # On macOS/Linux:
   python3 -m venv venv
   source venv/bin/activate

   # On Windows (PowerShell):
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   For running the test suite locally, also install the development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
### Environment Configuration

Create a `.env` file by copying the sample template:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Free key from https://api.nasa.gov/ (defaults to DEMO_KEY if left blank)
NASA_API_KEY=your_nasa_api_key_here

# Free key from https://api.le-systeme-solaire.net/generatekey.html (optional).
# Without it, the planets page serves a built-in dataset instead of live data.
SOLAR_SYSTEM_API_KEY=

# Flask environment
FLASK_ENV=development

# Cache configuration
CACHE_TYPE=SimpleCache
CACHE_DEFAULT_TIMEOUT=3600

# Secret key for session security
SECRET_KEY=change-this-in-production
```

### Running Locally

Launch the Flask development server:

```bash
python run.py
```

Open your browser to `http://localhost:5000` to explore SpaceBoard.

### Running Tests

Execute the automated test suite using `pytest`:

```bash
pytest
```

To run with verbose output:

```bash
pytest -v
```

---

## Deployment

SpaceBoard is a standard WSGI Flask application and runs on any Python 3.10+ host.

### Entry points

| File | Purpose |
| :--- | :--- |
| `run.py` | Local development server (`python run.py`) — enables the debugger |
| `wsgi.py` | Production WSGI callable, `wsgi:app` — used by gunicorn/uWSGI |

### With gunicorn

```bash
pip install gunicorn
gunicorn wsgi:app --bind 0.0.0.0:8000 --workers 2
```

### With Docker

```bash
docker compose up --build
# then open http://localhost:8000
```

Or build and run the image directly:

```bash
docker build -t spaceboard .
docker run -p 8000:8000 --env-file .env spaceboard
```

### Required environment variables

`SECRET_KEY` and `NASA_API_KEY` must be supplied in production — both fall back
to safe development defaults, and a placeholder key triggers the rate-limited
`DEMO_KEY` path. See `.env.example`.

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `NASA_API_KEY` | `DEMO_KEY` | Free from [api.nasa.gov](https://api.nasa.gov/) |
| `SOLAR_SYSTEM_API_KEY` | *(empty)* | Optional; enables live planet data instead of the built-in dataset |
| `SECRET_KEY` | dev default | **Set a strong unique value in production** |
| `FLASK_ENV` | `development` | |
| `CACHE_TYPE` | `SimpleCache` | In-memory; see notes below |
| `CACHE_DEFAULT_TIMEOUT` | `3600` | Seconds |

> **Note on caching:** the default `SimpleCache` is per-process in-memory. With
> multiple gunicorn workers, set `CACHE_TYPE=FileSystemCache` and
> `CACHE_DIR=/tmp/spaceboard-cache`, or back it with Redis, so NASA API rate
> limits are preserved across processes.

### Platform notes

- **Render / Railway / PythonAnywhere** — set the start command to
  `gunicorn wsgi:app --bind 0.0.0.0:$PORT` and provide the environment variables above.
- **Static files** are served directly by Flask via `app/static/`, so no separate
  static-file service or build step is required.

---

## Interactive Sky Map (`/sky/`)

The Sky Map renders a client-side planisphere directly in an HTML5 canvas:

- **Star Field**: 1,052 bright stars down to magnitude 4.5 based on Hipparcos catalog data (`stars.json`), with spectral coloring and labeling for prominent navigational stars.
- **Constellation Lines**: Stick-figure alignments connecting astronomical coordinates across major constellations (`constellations.json`), toggled via the side control panel.
- **Constellation Detection**: Accurate IAU constellation boundary resolution for celestial bodies via `Astronomy.Constellation(ra, dec)`.
- **Live Planetary Ephemeris**: Sun, Moon, and planetary positions (Mercury through Neptune, plus Pluto) computed on-the-fly with `astronomy-engine`, showing real-time horizon coordinates (altitude/azimuth).
- **Navigation Tools**:
  - Direction quick-buttons: **North**, **South**, **East**, **West**, **Zenith**, and **Nadir / Below**.
  - Zoom slider: Adjust field of view between 10° (narrow telescope view) and 180° (full hemisphere planisphere).
  - Time Controls: Local date-time picker and 24-hour time scrubbing slider to observe planetary motion and stellar transits.
  - Coordinate Readouts: Live Right Ascension (RA), Declination (Dec), Altitude, and Azimuth for the viewport center.
  - Object Details: Click any star or planet to inspect its magnitude, constellation, distance, and elevation.

---

## "Where to Find This Planet Tonight"

On the **Planets** page (`/planets/`), each solar system body includes a real-time observation card powered by `planet-tonight.js`:
- Uses the browser's Geolocation API (falling back to standard coordinates if denied).
- Calculates true topocentric horizontal coordinates (altitude and compass azimuth).
- Identifies the current host constellation and symbol.
- Reports real-time distance in Astronomical Units (AU).
- Computes upcoming rise and set times for your exact geographic coordinates.
- Displays friendly indicators when a planet is currently below the horizon.

---

## Architecture & Design Patterns

- **API Isolation & Resilience**: All external HTTP requests are encapsulated inside `app/api/`. Every function catches timeouts, HTTP errors, and connection drops, returning consistent structured dictionaries (`{"ok": True/False, "data": ..., "error": ...}`) so routes and templates never raise unhandled exceptions.
- **Rate-Limit Preservation**: NASA's free registered key allows up to 1,000 requests/hour (and `DEMO_KEY` only 30 requests/hour). Flask-Caching caches upstream responses (with sensible TTLs like 1 hour for daily APOD and planetary metrics, and 60 seconds for planet ephemeris feeds).
- **Zero-Build Frontend**: Tailwind CSS and `astronomy-engine` are loaded via high-availability CDNs, eliminating the need for Node.js, Webpack, or npm build pipelines while maintaining clean modular JavaScript.
- **Contract & Regression Testing**: `tests/test_constellations.py` ensures that all DOM IDs referenced in `sky.js` exist in `sky.html`, that the astronomy-engine CDN bundle exposes expected methods, and that constellation coordinate geometry matches the star catalog boundaries.

---

## Roadmap

- [x] MVP: Near-Earth Asteroid dashboard with hazard classification
- [x] Solar system planetary data integration
- [x] NASA Exoplanet Archive searchable database
- [x] Astronomy Picture of the Day on the home page
- [x] Server-side caching layer with graceful error fallbacks
- [x] Interactive 2D Sky Map with star catalog and real-time ephemeris
- [x] Constellation lines and IAU constellation detection
- [x] "Where to find this planet tonight" local observation module
- [x] Detail pages for planets, exoplanets, and asteroids
- [x] Glassmorphism design system
- [x] Automated unit and contract test suites
- [x] Cloud deployment configuration (Docker / gunicorn / Render / Railway)
- [ ] Progressive Web App (PWA) offline support (manifest + service worker)

---

## License

This project is licensed under the [MIT License](LICENSE).

