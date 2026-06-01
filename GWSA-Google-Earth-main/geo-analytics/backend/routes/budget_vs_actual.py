"""
GWSA GeoAnalytics — Actual vs Budget Route
GET /api/budget-vs-actual/<store_id>?start=YYYY-MM-DD&end=YYYY-MM-DD&grain=day|month
Daily Core revenue Actual vs Budget from DailyCoreRevenueBudgetVsActual_NoSubCategory.
"""
from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from middleware.security import (
    limiter, BudgetVsActualQuerySchema, require_valid_store
)
from config import Config

budget_vs_actual_bp = Blueprint('budget_vs_actual', __name__)


@budget_vs_actual_bp.route('/api/budget-vs-actual/<store_id>', methods=['GET'])
@limiter.limit("30 per minute")
@require_valid_store
def get_budget_vs_actual(store_id):
    if not Config.ENABLE_KPIS:
        return jsonify(error='KPI data is disabled for this environment'), 403

    schema = BudgetVsActualQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as err:
        return jsonify(error=err.messages), 400

    start = params['start'].isoformat()
    end = params['end'].isoformat()
    grain = params['grain']

    try:
        from db.queries import get_budget_vs_actual as db_get_budget_vs_actual
        data = db_get_budget_vs_actual(store_id, start, end, grain=grain)
        return jsonify(data)
    except Exception as e:
        return jsonify(error=str(e)), 500
