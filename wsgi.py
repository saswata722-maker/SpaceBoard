"""Production WSGI entry point.

Used by gunicorn / uWSGI / mod_wsgi:

    gunicorn wsgi:app --bind 0.0.0.0:8000 --workers 2

Kept separate from ``run.py`` so the development server's debugger and reloader
are never enabled by a production command line.
"""

from app import create_app

app = create_app()
