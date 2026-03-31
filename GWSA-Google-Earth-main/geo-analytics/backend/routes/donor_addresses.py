"""
GWSA GeoAnalytics — Donor Addresses Route
GET /api/donor-addresses/<store_id> — returns donor pins for Donor Map tab
"""
from flask import Blueprint, jsonify
from middleware.security import limiter, require_valid_store
from config import Config

donor_addresses_bp = Blueprint('donor_addresses', __name__)


@donor_addresses_bp.route('/api/donor-addresses/<store_id>', methods=['GET'])
@limiter.limit("30 per minute")
@require_valid_store
def get_donor_addresses(store_id):
    if Config.LOCATIONS_SOURCE == "static":
        return jsonify([])

    try:
        from db.queries import get_donor_addresses as db_get_donor_addresses
        data = db_get_donor_addresses(store_id)
        return jsonify(data)
    except Exception as e:
        return jsonify(error=str(e)), 500
