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
    if not Config.ENABLE_KPIS:
        return jsonify(error='KPI data is disabled for this environment'), 403

    schema = TrendsQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as err:
        return jsonify(error=err.messages), 400

    months = params['months']
    start = params.get('start')
    end = params.get('end')
    start_iso = start.isoformat() if start else None
    end_iso = end.isoformat() if end else None

    try:
        from db.queries import get_trends as db_get_trends
        if start_iso and end_iso:
            data = db_get_trends(store_id, months=months, start_date=start_iso, end_date=end_iso)
        else:
            data = db_get_trends(store_id, months=months)
        return jsonify(data)
    except Exception as e:
        return jsonify(error=str(e)), 500
