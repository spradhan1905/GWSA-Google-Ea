"""
GWSA GeoAnalytics — Flask Application
Goodwill Industries of San Antonio
Full-stack geospatial analytics platform.
v1.0 Demo
"""
import os
from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from middleware.security import limiter


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = Config.SECRET_KEY

    # ─── CORS ─────────────────────────────────
    CORS(app,
         origins=[Config.CORS_ORIGIN],
         methods=['GET', 'POST'],
         allow_headers=['Content-Type'],
         supports_credentials=False,
         max_age=3600)

    # ─── Rate Limiter ─────────────────────────
    limiter.init_app(app)

    # ─── Security Headers (skip Talisman in dev) ──
    if not Config.DEBUG:
        try:
            from flask_talisman import Talisman
            csp = {
                'default-src': "'self'",
                'script-src': ["'self'", "https://maps.googleapis.com", "https://maps.gstatic.com"],
                'style-src': ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
                'img-src': ["'self'", "data:", "https://*.googleapis.com", "https://*.gstatic.com"],
                'connect-src': ["'self'"],
                'frame-src': "'none'",
            }
            Talisman(app, force_https=False, strict_transport_security=True,
                     content_security_policy=csp,
                     referrer_policy='strict-origin-when-cross-origin')
        except ImportError:
            pass

    # ─── Register Blueprints ──────────────────
    from routes.locations import locations_bp
    from routes.financials import financials_bp
    from routes.door_count import door_count_bp
    from routes.trends import trends_bp
    from routes.chat import chat_bp
    from routes.donor_addresses import donor_addresses_bp

    app.register_blueprint(locations_bp)
    app.register_blueprint(financials_bp)
    app.register_blueprint(door_count_bp)
    app.register_blueprint(trends_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(donor_addresses_bp)

    # ─── Error Handlers ───────────────────────
    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify(error="Too many requests. Please slow down."), 429

    @app.errorhandler(404)
    def not_found(e):
        return jsonify(error="Endpoint not found"), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify(error="Internal server error"), 500

    # ─── Health Check ─────────────────────────
    @app.route('/api/health', methods=['GET'])
    def health():
        return jsonify({
            "status": "ok",
            "data_source": "sql",
            "sql_database": Config.SQL_DATABASE,
            "sql_sales_line_object": Config.SQL_SALES_LINE_OBJECT,
            "sql_locations_table": Config.SQL_LOCATIONS_TABLE,
            "sql_sales_core_category": Config.SQL_SALES_CORE_CATEGORY,
            "sql_sales_unit_name_flexible": Config.SQL_SALES_UNIT_NAME_FLEXIBLE,
            "sql_locations_minimal_join": Config.SQL_LOCATIONS_MINIMAL_JOIN,
            "locations_source": Config.LOCATIONS_SOURCE,
            "gemini_configured": bool(Config.GEMINI_API_KEY),
        })

    return app


if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', '5000'))
    print(f"\n  GWSA GeoAnalytics API")
    print(f"  http://localhost:{port}")
    print(f"  Metrics: SQL (SalesFact + static locations)")
    print(f"  Gemini: {'configured' if Config.GEMINI_API_KEY else 'not configured'}\n")
    app.run(host='0.0.0.0', port=port, debug=Config.DEBUG)
