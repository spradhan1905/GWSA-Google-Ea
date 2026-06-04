"""Fetch ACS 5-year estimates for all Texas census tracts (county-chunked)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from census.acs_variables import ACS_DATASET, ACS_GET_VARS, ACS_VINTAGE, TEXAS_STATE_FIPS


def _census_api_key() -> Optional[str]:
    key = (os.environ.get("CENSUS_API_KEY") or "").strip()
    return key or None


def _parse_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s in {"-666666666", "-888888888", "-999999999", "null"}:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _row_to_record(headers: List[str], row: List[str]) -> Dict[str, Any]:
    data = dict(zip(headers, row))
    state = str(data.get("state", "")).zfill(2)
    county = str(data.get("county", "")).zfill(3)
    tract = str(data.get("tract", "")).zfill(6)
    geoid = f"{state}{county}{tract}"

    pop = _parse_int(data.get("B01003_001E"))
    poverty_u = _parse_int(data.get("B17001_001E"))
    poverty_n = _parse_int(data.get("B17001_002E"))
    poverty_rate = None
    if poverty_u and poverty_u > 0 and poverty_n is not None:
        poverty_rate = round(100.0 * poverty_n / poverty_u, 1)

    return {
        "geoid": geoid,
        "name": data.get("NAME"),
        "median_income": _parse_int(data.get("B19013_001E")),
        "median_income_moe": _parse_int(data.get("B19013_001M")),
        "population": pop,
        "households": _parse_int(data.get("B19001_001E")),
        "poverty_rate_pct": poverty_rate,
        "median_home_value": _parse_int(data.get("B25077_001E")),
        "occupied_housing_units": _parse_int(data.get("B25003_001E")),
    }


def fetch_texas_tract_metrics(
    *,
    api_key: Optional[str] = None,
    timeout_sec: float = 120.0,
) -> Dict[str, Dict[str, Any]]:
    """
    Returns dict keyed by 11-digit tract GEOID.
    Pulls one county at a time to stay within Census API limits.
    """
    key = api_key if api_key is not None else _census_api_key()
    counties = _fetch_texas_county_fips(api_key=key, timeout_sec=timeout_sec)
    out: Dict[str, Dict[str, Any]] = {}
    var_param = ",".join(ACS_GET_VARS)

    for county in counties:
        params = {
            "get": var_param,
            "for": "tract:*",
            "in": f"state:{TEXAS_STATE_FIPS} county:{county}",
        }
        if key:
            params["key"] = key
        url = (
            f"https://api.census.gov/data/{ACS_VINTAGE}/{ACS_DATASET}?"
            + urllib.parse.urlencode(params)
        )
        payload = _http_json(url, timeout_sec=timeout_sec)
        if not payload or len(payload) < 2:
            continue
        headers = payload[0]
        for row in payload[1:]:
            rec = _row_to_record(headers, row)
            out[rec["geoid"]] = rec
    return out


def _fetch_texas_county_fips(*, api_key: Optional[str], timeout_sec: float) -> List[str]:
    params = {"get": "NAME", "for": "county:*", "in": f"state:{TEXAS_STATE_FIPS}"}
    if api_key:
        params["key"] = api_key
    url = (
        f"https://api.census.gov/data/{ACS_VINTAGE}/{ACS_DATASET}?"
        + urllib.parse.urlencode(params)
    )
    payload = _http_json(url, timeout_sec=timeout_sec)
    counties: List[str] = []
    if not payload or len(payload) < 2:
        return counties
    county_idx = payload[0].index("county")
    for row in payload[1:]:
        counties.append(str(row[county_idx]).zfill(3))
    return sorted(set(counties))


def _http_json(url: str, *, timeout_sec: float) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "GWSA-GeoAnalytics/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Census API HTTP {exc.code} for {url}: {body}") from exc
    if "Missing Key" in raw or "<html" in raw.lower()[:200]:
        raise RuntimeError(
            "Census API requires CENSUS_API_KEY in backend/.env. "
            "Sign up free: https://api.census.gov/data/key_signup.html"
        )
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Census API returned non-JSON for {url}: {raw[:300]}") from exc
