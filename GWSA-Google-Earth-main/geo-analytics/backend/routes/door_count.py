"""
GWSA GeoAnalytics — Door Count Route
GET /api/door-count/<store_id>?start=YYYY-MM-DD&end=YYYY-MM-DD
"""
from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from middleware.security import (
    limiter, DoorCountQuerySchema, require_valid_store
)

door_count_bp = Blueprint('door_count', __name__)


@door_count_bp.route('/api/door-count/<store_id>', methods=['GET'])
@limiter.limit("30 per minute")
@require_valid_store
def get_door_count(store_id):
    schema = DoorCountQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as err:
        return jsonify(error=err.messages), 400

    start = params['start'].isoformat()
    end = params['end'].isoformat()

    try:
        from db.queries import get_door_count as db_get_door_count
        data = db_get_door_count(store_id, start, end)
        return jsonify(data)
    except Exception as e:
        return jsonify(error=str(e)), 500
