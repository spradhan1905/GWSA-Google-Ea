"""Download Texas census tract boundaries (Census FTP with TIGERweb fallback)."""
from __future__ import annotations

import json
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

from census.acs_variables import TEXAS_STATE_FIPS, TRACT_BOUNDARY_URLS

_USER_AGENT = "GWSA-GeoAnalytics/1.0 (Goodwill SA GeoAnalytics)"
_TIGERWEB_QUERY = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/Tracts_Blocks/MapServer/0/query"
)
_TIGERWEB_BATCH_SIZE = 500


def download_tract_zip(dest: Path, *, timeout_sec: float = 600.0) -> Path:
    """Try each official TIGER/Line ZIP URL with retries; return path to zip."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    errors: List[str] = []

    for url in TRACT_BOUNDARY_URLS:
        for attempt in range(1, 3):
            try:
                print(f"  Trying {url} (attempt {attempt}/2)...")
                _download_once(url, dest, timeout_sec=timeout_sec)
                print(f"  Downloaded {dest.stat().st_size / (1024 * 1024):.1f} MB")
                return dest
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
                errors.append(f"{url} attempt {attempt}: {exc}")
                if attempt < 2:
                    time.sleep(2)
    raise RuntimeError(
        "Could not download tract boundaries from Census FTP.\n"
        + "\n".join(errors[-4:])
    )


def fetch_tract_feature_collection(
    *, timeout_sec: float = 180.0
) -> Tuple[Dict[str, Any], str]:
    """
    Texas tract polygons via Census TIGERweb (official .gov).
    Uses objectId batching — geojson + resultOffset is unreliable on this service.
    """
    object_ids = _fetch_texas_tract_object_ids(timeout_sec=timeout_sec)
    if not object_ids:
        raise RuntimeError("TIGERweb returned no object IDs for Texas tracts")

    all_features: List[dict] = []
    for i in range(0, len(object_ids), _TIGERWEB_BATCH_SIZE):
        chunk = object_ids[i : i + _TIGERWEB_BATCH_SIZE]
        params = {
            "objectIds": ",".join(str(oid) for oid in chunk),
            "outFields": "GEOID,NAME",
            "returnGeometry": "true",
            "f": "geojson",
            "outSR": "4326",
        }
        url = _TIGERWEB_QUERY + "?" + urllib.parse.urlencode(params)
        payload = _http_json(url, timeout_sec=timeout_sec)
        batch = payload.get("features") or []
        all_features.extend(batch)
        print(f"  TIGERweb tracts: {len(all_features)} / {len(object_ids)}...")

    if not all_features:
        raise RuntimeError(
            "TIGERweb returned no tract geometries. "
            "Check network access to tigerweb.geo.census.gov"
        )

    return (
        {"type": "FeatureCollection", "features": all_features},
        "Census TIGERweb Tracts_Blocks MapServer (layer 0)",
    )


def _fetch_texas_tract_object_ids(*, timeout_sec: float) -> List[int]:
    params = {
        "where": f"STATE='{TEXAS_STATE_FIPS}'",
        "returnIdsOnly": "true",
        "f": "json",
    }
    url = _TIGERWEB_QUERY + "?" + urllib.parse.urlencode(params)
    payload = _http_json(url, timeout_sec=timeout_sec)
    return list(payload.get("objectIds") or [])


def extract_shapefile_from_zip(zip_path: Path, extract_dir: Path) -> Path:
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    shp_files = list(extract_dir.glob("*.shp"))
    if not shp_files:
        raise RuntimeError(f"No .shp in {zip_path}")
    return shp_files[0]


def _download_once(url: str, dest: Path, *, timeout_sec: float) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        if resp.status >= 400:
            raise urllib.error.HTTPError(
                url, resp.status, resp.reason, resp.headers, None
            )
        with open(dest, "wb") as fh:
            shutil.copyfileobj(resp, fh)
    if dest.stat().st_size < 10_000:
        raise RuntimeError(
            f"Download too small ({dest.stat().st_size} bytes) — likely an error page"
        )


def _http_json(url: str, *, timeout_sec: float) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    if not raw.strip():
        raise RuntimeError(f"Empty response from {url}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON from {url}: {raw[:200]}") from exc
