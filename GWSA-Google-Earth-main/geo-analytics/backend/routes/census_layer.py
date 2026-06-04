"""
Serve pre-built Texas census tract income GeoJSON for map hover layers.

Build data first:
  cd backend && python scripts/build_texas_census_tract_layer.py

Query params:
  scope=full   — all Texas tracts (~7k, large; desktop)
  scope=metro  — San Antonio metro counties only (mobile-friendly)
"""
from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from middleware.security import limiter

census_layer_bp = Blueprint("census_layer", __name__)

_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "census"
_SCOPES = {
    "full": {
        "geojson": _DATA_DIR / "texas_tracts_acs.geojson",
        "gzip": _DATA_DIR / "texas_tracts_acs.geojson.gz",
    },
    "metro": {
        "geojson": _DATA_DIR / "texas_tracts_acs_metro.geojson",
        "gzip": _DATA_DIR / "texas_tracts_acs_metro.geojson.gz",
    },
}
_META = _DATA_DIR / "texas_tracts_acs.meta.json"


def _resolve_scope() -> str:
    scope = (request.args.get("scope") or "full").strip().lower()
    return scope if scope in _SCOPES else "full"


def _send_geojson(scope: str):
    paths = _SCOPES[scope]
    geo_path = paths["geojson"]
    gz_path = paths["gzip"]
    if not geo_path.is_file():
        return jsonify(
            error="Census layer not built",
            scope=scope,
            hint="Run: python scripts/build_texas_census_tract_layer.py",
        ), 404

    accept = (request.headers.get("Accept-Encoding") or "").lower()
    if "gzip" in accept and gz_path.is_file():
        resp = send_file(
            gz_path,
            mimetype="application/geo+json",
            as_attachment=False,
            conditional=True,
            etag=True,
            max_age=86400,
        )
        resp.headers["Content-Encoding"] = "gzip"
        resp.headers["Vary"] = "Accept-Encoding"
        return resp

    return send_file(
        geo_path,
        mimetype="application/geo+json",
        as_attachment=False,
        conditional=True,
        etag=True,
        max_age=86400,
    )


@census_layer_bp.route("/api/census/texas-tract-income/meta", methods=["GET"])
@limiter.limit("120 per minute")
def texas_tract_income_meta():
    if not _META.is_file():
        return jsonify(
            error="Census layer not built",
            hint="Run: python scripts/build_texas_census_tract_layer.py",
        ), 404
    with open(_META, encoding="utf-8") as fh:
        payload = json.load(fh)
    scope = _resolve_scope()
    if scope == "metro" and payload.get("metro_scope"):
        metro = payload["metro_scope"]
        payload = {
            **payload,
            "scope": "metro",
            "feature_count": metro.get("feature_count"),
            "income_breaks": metro.get("income_breaks") or payload.get("income_breaks"),
            "geography_label": metro.get("name", "San Antonio metro"),
        }
    else:
        payload = {**payload, "scope": "full"}
    return jsonify(payload)


@census_layer_bp.route("/api/census/texas-tract-income", methods=["GET"])
@limiter.limit("30 per minute")
def texas_tract_income_geojson():
    return _send_geojson(_resolve_scope())
