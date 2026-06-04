"""
Serve pre-built Texas census tract income GeoJSON for map hover layers.

Build data first:
  cd backend && python scripts/build_texas_census_tract_layer.py
"""
from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, jsonify, send_file

from middleware.security import limiter

census_layer_bp = Blueprint("census_layer", __name__)

_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "census"
_GEOJSON = _DATA_DIR / "texas_tracts_acs.geojson"
_META = _DATA_DIR / "texas_tracts_acs.meta.json"


@census_layer_bp.route("/api/census/texas-tract-income/meta", methods=["GET"])
@limiter.limit("120 per minute")
def texas_tract_income_meta():
    if not _META.is_file():
        return jsonify(
            error="Census layer not built",
            hint="Run: python scripts/build_texas_census_tract_layer.py",
        ), 404
    with open(_META, encoding="utf-8") as fh:
        return jsonify(json.load(fh))


@census_layer_bp.route("/api/census/texas-tract-income", methods=["GET"])
@limiter.limit("30 per minute")
def texas_tract_income_geojson():
    if not _GEOJSON.is_file():
        return jsonify(
            error="Census layer not built",
            hint="Run: python scripts/build_texas_census_tract_layer.py",
        ), 404
    return send_file(
        _GEOJSON,
        mimetype="application/geo+json",
        as_attachment=False,
        conditional=True,
        etag=True,
        max_age=86400,
    )
