import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # The debugger is enabled only when explicitly opted in, so that running
    # `python run.py` against a production configuration cannot expose the
    # Werkzeug console. Production deployments use `wsgi:app`.
    debug = os.getenv("FLASK_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}

    if debug:
        app.run(debug=True, use_reloader=True)
    else:
        # Default to a quiet dev server on 5000, matching Flask's convention.
        app.run(debug=False, use_reloader=False)
