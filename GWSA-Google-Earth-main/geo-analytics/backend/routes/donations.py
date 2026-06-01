"""
GWSA GeoAnalytics — Donations Route
GET /api/donations/<store_id>?start=YYYY-MM-DD&end=YYYY-MM-DD
Daily donation totals (SUM DonationAmt) from tbl_Donation.
"""
from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from middleware.security import (
    limiter, DonationsQuerySchema, require_valid_store
)
from config import Config

donations_bp = Blueprint('donations', __name__)


@donations_bp.route('/api/donations/<store_id>', methods=['GET'])
@limiter.limit("30 per minute")
@require_valid_store
def get_donations(store_id):
    if not Config.ENABLE_KPIS:
        return jsonify(error='KPI data is disabled for this environment'), 403

    schema = DonationsQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as err:
        return jsonify(error=err.messages), 400

    start = params['start'].isoformat()
    end = params['end'].isoformat()

    try:
        from db.queries import get_donations as db_get_donations
        data = db_get_donations(store_id, start, end)
        return jsonify(data)
    except Exception as e:
        return jsonify(error=str(e)), 500
