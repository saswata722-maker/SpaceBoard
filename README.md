# SpaceBoard 🌌

A Flask web app to explore the solar system, exoplanets, and the night sky using NASA's public data APIs and an interactive 2D planisphere.

## Overview

SpaceBoard lets users browse:
- **Asteroids** — near-Earth objects (NEOs) with hazard classification, size, and close-approach data
- **Planets** — solar system planets plus a searchable exoplanet database
- **Stars** — stellar imagery from NASA's Astronomy Picture of the Day (APOD)
- **Sky Map** — interactive 2D planisphere showing stars and real-time planet positions

Built with future portfolio use in mind — code stays clean, documented, and demo-ready.

## Features

- [x] Home page with NASA's Astronomy Picture of the Day (APOD)
- [x] Asteroid dashboard: list/table of NEOs, filter by date range and hazardous status
- [x] Planet info pages: solar system planets (mass, radius, moons, etc.)
- [x] Exoplanet search using NASA Exoplanet Archive
- [x] Star data/imagery section (APOD gallery)
- [x] Server-side caching to stay within NASA's free-tier rate limits
- [x] Graceful fallback UI if a NASA API call fails or is rate-limited
- [x] Responsive design (mobile + desktop)
- [x] Interactive 2D Sky Map with star catalog and real-time planet positions
- [ ] Constellation lines and boundary detection on the sky map
- [ ] Planets page: "where to find this planet tonight" sky-position info
- [ ] Sky map unit tests

## Tech Stack

- **Backend:** Python (Flask)
- **Templating:** Jinja2
- **Styling:** Tailwind CSS (via CDN — no Node build step needed)
- **Caching:** Flask-Caching (SimpleCache, 1-hour TTL)
- **HTTP client:** `requests`
- **Config/env:** `python-dotenv`
- **Sky Map:** astronomy-engine (CDN) for client-side ephemeris, Canvas 2D rendering
- **APIs:**
  - [NASA NeoWs](https://api.nasa.gov/) — Near Earth Object Web Service
  - [NASA APOD](https://api.nasa.gov/) — Astronomy Picture of the Day
  - [NASA Exoplanet Archive](https://exoplanetarchive.ipac.caltech.edu/) — exoplanet data
  - [Solar System OpenData API](https://api.le-systeme-solaire.net/) — solar system body data

## Getting Started

### Prerequisites

- Python 3.10+
- A free NASA API key from [api.nasa.gov](https://api.nasa.gov/) (optional — the app falls back to `DEMO_KEY` if none is set, but rate limits are much lower)

### Installation

```bash
git clone <your-repo-url>
cd SpaceBoard
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Environment Variables

Copy `.env.example` to `.env` and add your NASA API key:

```bash
cp .env.example .env
```

```
NASA_API_KEY=your_api_key_here
FLASK_ENV=development
```

### Run Locally

```bash
python run.py
```

App will be available at `http://localhost:5000`

## Sky Map

The Sky Map (`/sky/`) is an interactive 2D planisphere that renders:
- **1,052 stars** from a Hipparcos-derived catalog (magnitude ≤ 4.5), with named stars labeled
- **Real-time planet positions** via the astronomy-engine library (client-side ephemeris, no API key needed)
- **Sun and Moon** positions
- **Controls:** latitude/longitude inputs, geolocation button, UTC time picker + scrubber, view direction buttons (N/S/E/W/Zenith/Below), zoom slider (10°–180°), and display toggles (planets, ecliptic, grid lines, star names)

### Known Sky Map Limitations

- **Constellation detection** is approximate — it finds the nearest named star's constellation rather than using actual constellation boundaries. Constellation boundary data is planned but not yet implemented.
- **No constellation lines** are drawn on the canvas yet.
- **No unit tests** exist for the sky map route or planet-positions API yet.

## Project Structure

See [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) for a full breakdown of folders and files.

## Design Notes

- **Caching**: NASA's free API key has a rate limit (1,000 requests/hour). Flask-Caching wraps API calls so repeated requests within the TTL window are served from memory instead of hitting NASA again.
- **Error handling**: each `app/api/` module catches request failures and returns a consistent fallback shape, so the UI can show a friendly "data unavailable" state instead of crashing.
- **Styling**: Tailwind is loaded via CDN script tag in `base.html` — gets the utility-class workflow without adding Node/npm as a build dependency.
- **DEMO_KEY fallback**: if no `NASA_API_KEY` is set in your `.env`, the app automatically falls back to NASA's `DEMO_KEY` so it runs immediately. Note that DEMO_KEY has a much lower rate limit (~30 requests/hour) than a registered key. For production or heavy use, get a free key at [api.nasa.gov](https://api.nasa.gov/).
- **Sky Map ephemeris**: the sky map uses the astronomy-engine JavaScript library (loaded via CDN) for client-side planetary position calculations. This avoids additional API calls and works without a NASA API key.
- **PWA (offline support)**: intentionally deferred. It's a nice future enhancement but adds real complexity (service worker, cache invalidation) that isn't needed for a v1 personal project.

## Roadmap

- [x] MVP: Asteroid dashboard working end-to-end
- [x] Add planet section
- [x] Add exoplanet search
- [x] Add stars section
- [x] Add server-side caching layer
- [x] Polish UI / responsive design
- [x] Add interactive 2D Sky Map with star catalog
- [x] Add real-time planet positions to sky map
- [ ] Add constellation boundary data and lines to sky map
- [ ] Add "where to find this planet tonight" to planets page
- [ ] Add sky map unit tests
- [ ] (Future) PWA support — installable, offline caching
- [ ] Deploy (Render/PythonAnywhere/Railway)

## License

MIT
