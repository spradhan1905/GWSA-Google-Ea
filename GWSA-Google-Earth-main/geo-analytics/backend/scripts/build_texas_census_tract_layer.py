"""
Build Texas census-tract GeoJSON with ACS median income + related metrics.

Prerequisites:
  pip install pyshp  (only if Census ZIP download succeeds)
  CENSUS_API_KEY in backend/.env (free: https://api.census.gov/data/key_signup.html)

Run from geo-analytics/backend:
  python scripts/build_texas_census_tract_layer.py

Output:
  data/census/texas_tracts_acs.geojson
  data/census/texas_tracts_acs.meta.json
"""
from __future__ import annotations

import gzip
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(BACKEND_ROOT / ".env")
except ImportError:
    pass

from census.acs_client import fetch_texas_tract_metrics  # noqa: E402
from census.acs_variables import ACS_VINTAGE  # noqa: E402
from census.boundary_fetch import (  # noqa: E402
    download_tract_zip,
    extract_shapefile_from_zip,
    fetch_tract_feature_collection,
)

OUT_DIR = BACKEND_ROOT / "data" / "census"
GEOJSON_PATH = OUT_DIR / "texas_tracts_acs.geojson"
GEOJSON_GZ_PATH = OUT_DIR / "texas_tracts_acs.geojson.gz"
META_PATH = OUT_DIR / "texas_tracts_acs.meta.json"
METRICS_CACHE_PATH = OUT_DIR / "texas_tract_metrics_cache.json"


def _load_tract_shapes(shp_path: Path):
    try:
        import shapefile  # pyshp
    except ImportError as exc:
        raise SystemExit("pyshp is required for shapefile mode: pip install pyshp") from exc

    reader = shapefile.Reader(str(shp_path))
    field_names = [f[0] for f in reader.fields[1:]]
    geoid_idx = field_names.index("GEOID") if "GEOID" in field_names else None
    name_idx = field_names.index("NAMELSAD") if "NAMELSAD" in field_names else None

    for sr in reader.iterShapeRecords():
        geoid = (
            str(sr.record[geoid_idx]).strip()
            if geoid_idx is not None
            else None
        )
        if not geoid:
            state = str(sr.record[field_names.index("STATEFP")]).zfill(2)
            county = str(sr.record[field_names.index("COUNTYFP")]).zfill(3)
            tract = str(sr.record[field_names.index("TRACTCE")]).zfill(6)
            geoid = f"{state}{county}{tract}"
        label = (
            str(sr.record[name_idx]).strip()
            if name_idx is not None
            else geoid
        )
        yield geoid, label, sr.shape


def _shape_to_geojson_geometry(shape) -> Optional[dict]:
    # pyshp: 5 = POLYGON, 15 = POLYGONZ, 25 = POLYGONM
    if shape.shapeType not in (5, 15, 25):
        return None
    rings = []
    parts = list(shape.parts) + [len(shape.points)]
    for i in range(len(parts) - 1):
        pts = shape.points[parts[i] : parts[i + 1]]
        if len(pts) < 4:
            continue
        ring = [[float(x), float(y)] for x, y in pts]
        rings.append(ring)
    if not rings:
        return None
    if len(rings) == 1:
        return {"type": "Polygon", "coordinates": rings}
    return {"type": "MultiPolygon", "coordinates": [[r] for r in rings]}


def _feature_from_shape(
    geoid: str, label: str, shape, metrics: Dict[str, Dict[str, Any]]
) -> Optional[dict]:
    geom = _shape_to_geojson_geometry(shape)
    if not geom:
        return None
    return _feature_from_geom(geoid, label, geom, metrics)


def _feature_from_geom(
    geoid: str,
    label: str,
    geom: dict,
    metrics: Dict[str, Dict[str, Any]],
) -> dict:
    m = metrics.get(geoid, {})
    income = m.get("median_income")
    return {
        "type": "Feature",
        "geometry": geom,
        "properties": {
            "geoid": geoid,
            "label": m.get("name") or label,
            "median_income": income,
            "median_income_moe": m.get("median_income_moe"),
            "population": m.get("population"),
            "households": m.get("households"),
            "poverty_rate_pct": m.get("poverty_rate_pct"),
            "median_home_value": m.get("median_home_value"),
            "occupied_housing_units": m.get("occupied_housing_units"),
        },
    }


def _income_breaks(values: list[int]) -> list[int]:
    vals = sorted(v for v in values if v and v > 0)
    if len(vals) < 5:
        return [0, 35000, 55000, 75000, 100000, max(vals) if vals else 150000]
    qs = [0]
    for q in (0.2, 0.4, 0.6, 0.8, 1.0):
        idx = min(len(vals) - 1, int(round(q * (len(vals) - 1))))
        qs.append(vals[idx])
    cleaned = [qs[0]]
    for v in qs[1:]:
        cleaned.append(max(v, cleaned[-1] + 1))
    return cleaned


def _build_features_from_zip(
    metrics: Dict[str, Dict[str, Any]], tmp: Path
) -> Tuple[List[dict], str]:
    zpath = tmp / "tracts.zip"
    print("Downloading tract boundaries from Census FTP...")
    download_tract_zip(zpath)
    shp_path = extract_shapefile_from_zip(zpath, tmp)
    features = []
    for geoid, label, shape in _load_tract_shapes(shp_path):
        feat = _feature_from_shape(geoid, label, shape, metrics)
        if feat:
            features.append(feat)
    return features, "U.S. Census cartographic tract shapefile (ZIP)"


def _build_features_from_tigerweb(
    metrics: Dict[str, Dict[str, Any]],
) -> Tuple[List[dict], str]:
    print("Downloading tract boundaries from Census TIGERweb (FTP unavailable)...")
    fc, source = fetch_tract_feature_collection()
    features = []
    for raw in fc.get("features") or []:
        props = raw.get("properties") or {}
        geoid = str(props.get("GEOID") or "").strip()
        if not geoid:
            continue
        label = props.get("NAMELSAD") or props.get("NAME") or geoid
        geom = raw.get("geometry")
        if not geom:
            continue
        features.append(_feature_from_geom(geoid, str(label), geom, metrics))
    return features, source


def main() -> None:
    import os

    if not (os.environ.get("CENSUS_API_KEY") or "").strip():
        raise SystemExit(
            "Set CENSUS_API_KEY in backend/.env (free key: "
            "https://api.census.gov/data/key_signup.html)"
        )

    refresh_acs = os.environ.get("REFRESH_ACS", "").strip().lower() in ("1", "true", "yes")
    if METRICS_CACHE_PATH.is_file() and not refresh_acs:
        print(f"Loading cached ACS metrics from {METRICS_CACHE_PATH.name}...")
        with open(METRICS_CACHE_PATH, encoding="utf-8") as fh:
            metrics = json.load(fh)
    else:
        print("Fetching ACS tract metrics for Texas (all counties)...")
        metrics = fetch_texas_tract_metrics()
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(METRICS_CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump(metrics, fh)
    print(f"  ACS rows: {len(metrics)}")

    # Prefer TIGERweb when FTP is slow/blocked; ZIP is optional fast path if download works.
    boundary_source = ""
    features = []
    try:
        features, boundary_source = _build_features_from_tigerweb(metrics)
    except Exception as web_err:
        print(f"  TIGERweb failed ({web_err}). Trying Census TIGER/Line ZIP...")
        with tempfile.TemporaryDirectory() as tmp:
            features, boundary_source = _build_features_from_zip(metrics, Path(tmp))

    incomes = [
        f["properties"]["median_income"]
        for f in features
        if f["properties"].get("median_income")
    ]

    fc = {"type": "FeatureCollection", "features": features}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(GEOJSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(fc, fh, separators=(",", ":"))
    with gzip.open(GEOJSON_GZ_PATH, "wt", encoding="utf-8") as fh:
        json.dump(fc, fh, separators=(",", ":"))

    meta = {
        "geography": "census_tract",
        "state": "Texas",
        "state_fips": "48",
        "acs_vintage": ACS_VINTAGE,
        "dataset": "acs/acs5",
        "feature_count": len(features),
        "metrics": [
            "median_income",
            "median_income_moe",
            "population",
            "households",
            "poverty_rate_pct",
            "median_home_value",
            "occupied_housing_units",
        ],
        "income_breaks": _income_breaks(incomes),
        "source": {
            "income": f"U.S. Census ACS 5-Year {ACS_VINTAGE}",
            "boundaries": boundary_source,
        },
        "license": "Public domain (U.S. Census Bureau)",
    }
    with open(META_PATH, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    size_mb = GEOJSON_PATH.stat().st_size / (1024 * 1024)
    gz_mb = GEOJSON_GZ_PATH.stat().st_size / (1024 * 1024)
    print(f"Wrote {GEOJSON_PATH} ({size_mb:.1f} MB, {len(features)} tracts)")
    print(f"Wrote {GEOJSON_GZ_PATH} ({gz_mb:.1f} MB gzip)")
    print(f"Wrote {META_PATH}")


if __name__ == "__main__":
    main()
