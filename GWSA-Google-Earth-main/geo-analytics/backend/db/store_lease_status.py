"""
Retail store lease status (LEASE / OWN) from Agency 2025 square-foot spreadsheet.
Keyed by app location id (Storeid). Update when the spreadsheet changes.
"""
from typing import Optional

# Generated via scripts/build_lease_map.py; manual fixes for naming mismatches.
LEASE_STATUS_BY_STORE_ID = {
    "119": "LEASE",
    "120": "OWN",
    "121": "LEASE",
    "123": "LEASE",
    "124": "OWN",
    "125": "OWN",
    "126": "LEASE",
    "127": "LEASE",
    "128": "OWN",
    "129": "LEASE",
    "130": "LEASE",
    "131": "LEASE",
    "139": "OWN",
    "144": "LEASE",
    "145": "OWN",
    "146": "OWN",
    "147": "OWN",
    "150": "OWN",
    "151": "OWN",
    "152": "LEASE",
    "153": "LEASE",
    "154": "LEASE",
    "155": "LEASE",
    "156": "OWN",
    "157": "OWN",
    "158": "OWN",
    "159": "OWN",
    "160": "OWN",
    "165": "LEASE",
    "166": "LEASE",
    "183": "OWN",
    "184": "LEASE",
    "186": "LEASE",
    "188": "LEASE",
    "192": "LEASE",
    "194": "LEASE",
    "115": "OWN",
}


def lease_status_for_store(store_id: str) -> Optional[str]:
    sid = (store_id or "").strip()
    if not sid or sid.upper() == "CONSOLIDATED":
        return None
    return LEASE_STATUS_BY_STORE_ID.get(sid)
