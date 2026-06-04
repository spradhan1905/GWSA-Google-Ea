"""
GWSA GeoAnalytics — Key Metrics Route
GET /api/key-metrics/<store_id>?as_of=YYYY-MM-DD
"""
from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from middleware.security import (
    limiter, KeyMetricsQuerySchema, require_valid_store
)
from config import Config

key_metrics_bp = Blueprint('key_metrics', __name__)


@key_metrics_bp.route('/api/key-metrics/<store_id>', methods=['GET'])
@limiter.limit("30 per minute")
@require_valid_store
def get_key_metrics_route(store_id):
    if not Config.ENABLE_KPIS:
        return jsonify(error='KPI data is disabled for this environment'), 403

    schema = KeyMetricsQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as err:
        return jsonify(error=err.messages), 400

    as_of = params.get('as_of')
    as_of_iso = as_of.isoformat() if as_of else None

    try:
        from db.queries import get_key_metrics as db_get_key_metrics
        data = db_get_key_metrics(store_id, as_of=as_of_iso)
        if data.get('error'):
            return jsonify(data), 404
        return jsonify(data)
    except Exception as e:
        return jsonify(error=str(e)), 500
