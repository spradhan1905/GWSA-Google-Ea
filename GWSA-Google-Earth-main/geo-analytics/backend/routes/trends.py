"""
GWSA GeoAnalytics — Trends Route
GET /api/trends/<store_id>?months=12
"""
from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from middleware.security import (
    limiter, TrendsQuerySchema, require_valid_store
)
from config import Config

trends_bp = Blueprint('trends', __name__)


@trends_bp.route('/api/trends/<store_id>', methods=['GET'])
@limiter.limit("30 per minute")
@require_valid_store
def get_trends(store_id):
    schema = TrendsQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as err:
        return jsonify(error=err.messages), 400

    months = params['months']

    if Config.LOCATIONS_SOURCE == "static":
        return jsonify([])

    try:
        from db.queries import get_trends as db_get_trends
        data = db_get_trends(store_id, months)
        return jsonify(data)
    except Exception as e:
        return jsonify(error=str(e)), 500
