"""
GWSA GeoAnalytics — Locations Route
GET /api/locations — returns all active locations
"""
from flask import Blueprint, jsonify
from middleware.security import limiter
from config import Config

locations_bp = Blueprint('locations', __name__)


@locations_bp.route('/api/locations', methods=['GET'])
@limiter.limit("60 per minute")
def get_locations():
    if Config.DEMO_MODE:
        from db.mock_data import MOCK_LOCATIONS
        return jsonify(MOCK_LOCATIONS)

    try:
        from db.queries import get_locations as db_get_locations
        data = db_get_locations()
        return jsonify(data)
    except Exception as e:
        return jsonify(error=str(e)), 500
