"""
GWSA GeoAnalytics — Financials Route
GET /api/financials/<store_id>?start=YYYY-MM-DD&end=YYYY-MM-DD
"""
from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from middleware.security import (
    limiter, FinancialsQuerySchema, require_valid_store
)
from config import Config

financials_bp = Blueprint('financials', __name__)


@financials_bp.route('/api/financials/<store_id>', methods=['GET'])
@limiter.limit("30 per minute")
@require_valid_store
def get_financials(store_id):
    schema = FinancialsQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as err:
        return jsonify(error=err.messages), 400

    start = params['start'].isoformat()
    end = params['end'].isoformat()

    if Config.DEMO_MODE:
        from db.mock_data import get_mock_financials
        data = get_mock_financials(store_id, start, end)
        return jsonify(data)

    try:
        from db.queries import get_financials as db_get_financials
        data = db_get_financials(store_id, start, end)
        return jsonify(data)
    except Exception as e:
        return jsonify(error=str(e)), 500
