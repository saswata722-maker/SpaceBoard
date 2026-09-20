from flask import Flask, render_template

from app.cache import cache
from config import Config


def create_app():
    """Flask application factory."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize server-side cache
    cache.init_app(app)

    # Register blueprints
    from app.routes.asteroids import asteroids_bp
    from app.routes.home import home_bp
    from app.routes.planets import planets_bp
    from app.routes.stars import stars_bp
    from app.routes.sky import sky_bp

    app.register_blueprint(home_bp)
    app.register_blueprint(asteroids_bp)
    app.register_blueprint(planets_bp)
    app.register_blueprint(stars_bp)
    app.register_blueprint(sky_bp)

    # Custom error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_error(e):
        return render_template("500.html"), 500

    return app

