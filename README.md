# NASA Explorer 🌌

A web app to explore stars, asteroids, and planets using NASA's public data APIs.

## Overview

NASA Explorer lets users browse:
- **Asteroids** — near-Earth objects (NEOs) with hazard classification, size, and close-approach data
- **Planets** — solar system planets plus a searchable exoplanet database
- **Stars** — stellar imagery and data from NASA's Astronomy Picture of the Day and star catalogs

This started as a personal interest project and is being built with future portfolio use in mind — so code should stay clean, documented, and demo-ready.

## Features

- [ ] Home page with NASA's Astronomy Picture of the Day (APOD)
- [ ] Asteroid dashboard: list/table of NEOs, filter by date range and hazardous status
- [ ] Planet info pages: solar system planets (mass, radius, moons, etc.)
- [ ] Exoplanet search using NASA Exoplanet Archive
- [ ] Star data/imagery section
- [ ] Server-side caching to stay within NASA's free-tier rate limits
- [ ] Graceful fallback UI if a NASA API call fails or is rate-limited
- [ ] Responsive design (mobile + desktop)

## Tech Stack

- **Backend:** Python (Flask)
- **Templating:** Jinja2
- **Styling:** Tailwind CSS (via CDN — no Node build step needed)
- **Caching:** Flask-Caching (SimpleCache, 1-hour TTL)
- **HTTP client:** `requests`
- **Config/env:** `python-dotenv`
- **APIs:**
  - [NASA NeoWs](https://api.nasa.gov/) — Near Earth Object Web Service
  - [NASA APOD](https://api.nasa.gov/) — Astronomy Picture of the Day
  - [NASA Exoplanet Archive](https://exoplanetarchive.ipac.caltech.edu/) — exoplanet data
  - [Solar System OpenData API](https://api.le-systeme-solaire.net/) — solar system body data

## Getting Started

### Prerequisites

- Python 3.10+
- A free NASA API key from [api.nasa.gov](https://api.nasa.gov/)

### Installation

```bash
git clone <your-repo-url>
cd nasa-explorer
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

## Project Structure

See [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) for a full breakdown of folders and files.

## Design Notes

- **Caching**: NASA's free API key has a rate limit (1,000 requests/hour). Flask-Caching wraps API calls so repeated requests within the TTL window are served from memory instead of hitting NASA again.
- **Error handling**: each `app/api/` module catches request failures and returns a consistent fallback shape, so the UI can show a friendly "data unavailable" state instead of crashing.
- **Styling**: Tailwind is loaded via CDN script tag in `base.html` — gets the utility-class workflow without adding Node/npm as a build dependency.
- **DEMO_KEY fallback**: if no `NASA_API_KEY` is set in your `.env`, the app automatically falls back to NASA's `DEMO_KEY` so it runs immediately. Note that DEMO_KEY has a much lower rate limit (~30 requests/hour) than a registered key. For production or heavy use, get a free key at [api.nasa.gov](https://api.nasa.gov/).
- **PWA (offline support)**: intentionally deferred. It's a nice future enhancement but adds real complexity (service worker, cache invalidation) that isn't needed for a v1 personal project.

## Roadmap

- [ ] MVP: Asteroid dashboard working end-to-end
- [ ] Add planet section
- [ ] Add exoplanet search
- [ ] Add stars section
- [ ] Add server-side caching layer
- [ ] Polish UI / responsive design
- [ ] (Future) PWA support — installable, offline caching
- [ ] Deploy (Render/PythonAnywhere/Railway)

## License

MIT
