"""
GWSA GeoAnalytics — Financials Route
GET /api/financials/<store_id>?start=YYYY-MM-DD&end=YYYY-MM-DD
"""
from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from middleware.security import (
    limiter, FinancialsQuerySchema, require_valid_store
)
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
    this_month = params['this_month']

    try:
        from db.queries import get_financials as db_get_financials
        data = db_get_financials(store_id, start, end, this_month=this_month)
        return jsonify(data)
    except Exception as e:
        return jsonify(error=str(e)), 500
