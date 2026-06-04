"""Geography scopes for census tract map layers."""
from __future__ import annotations

from typing import Optional

# San Antonio metro area counties (Texas state FIPS 48 + county FIPS).
SAN_ANTONIO_METRO_COUNTY_FIPS = frozenset({
    "029",  # Bexar
    "091",  # Comal
    "094",  # Guadalupe
    "247",  # Wilson
    "259",  # Kendall
    "325",  # Medina
    "019",  # Bandera
})


def tract_county_fips(geoid: str) -> Optional[str]:
    """Return 3-digit county FIPS from an 11-digit census tract GEOID."""
    g = (geoid or "").strip()
    if len(g) < 5:
        return None
    return g[2:5]
