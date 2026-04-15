"""
Static store list — mirrors frontend/src/data/stores.js when there is no dbo.Locations in SQL.
Optional per-store GP keys (SoldStoreId, SalesStoreUnit, SalesUnitName) improve MTD matching.
Fill keys from JS_API.dbo.SalesFactFinal (DISTINCT SoldStoreId, [sales unit name], [sales store unit]).

Retail / outlet and donation-station LocationID values match PeopleCounter / org store-id lists.

Optional pcounter_location_ids: only if a site uses multiple PCounter LocationIDs (rare if Left/Right share one ID).
"""
from typing import Any, Dict, List, Optional

_RAW: List[Dict[str, Any]] = [
    {"id": "130", "name": "Garden Ridge Donation Station", "type": "adc", "address": "5580 FM 3009, Schertz, San Antonio, Texas, 78154", "lat": None, "lng": None},
    {"id": "131", "name": "Churchill Estates Donation Station", "type": "adc", "address": "15502 Huebner Rd, San Antonio, Texas, 78248", "lat": None, "lng": None},
    {"id": "139", "name": "Bandera Landing II Donation Station", "type": "adc", "address": "8010 Bandera Rd, San Antonio, Texas, 78250", "lat": None, "lng": None},
    {"id": "144", "name": "Leon Springs Donation Station", "type": "adc", "address": "24200 IH 10 West, Suite 103, San Antonio, Texas, 78257", "lat": None, "lng": None},
    {"id": "165", "name": "SOHO Donation Station", "type": "adc", "address": "19903 Stone Oak Pkwy, Suite 111, San Antonio, Texas, 78258", "lat": None, "lng": None},
    {"id": "166", "name": "Oak Park Donation Station", "type": "adc", "address": "8001 N New Braunfels Ave, San Antonio, Texas, 78209", "lat": None, "lng": None},
    {"id": "192", "name": "Parkwood Place Donation Station", "type": "adc", "address": "2235 Thousand Oaks Dr, San Antonio TX 78232", "lat": None, "lng": None},
    {"id": "194", "name": "Lakeside Plaza Donation Station", "type": "adc", "address": "26212 Canyon Golf Rd, Suite 103, San Antonio, Texas, 78260", "lat": None, "lng": None},
    {"id": "154", "name": "Austin Hwy Retail Store", "type": "store", "address": "1533 Austin Highway, San Antonio, Texas 78218, USA", "lat": None, "lng": None},
    {"id": "147", "name": "Bandera Retail Store", "type": "store", "address": "11722 Quincy Lee Drive, San Antonio, Texas 78249, USA", "lat": None, "lng": None},
    {"id": "150", "name": "Bitters Retail Store", "type": "store", "address": "13311 San Pedro Avenue, San Antonio, TX, USA", "lat": None, "lng": None},
    {"id": "146", "name": "Blanco North Retail Store", "type": "store", "address": "18478 Blanco Rd, San Antonio, Texas 78258, USA", "lat": None, "lng": None},
    {"id": "125", "name": "Blanco Retail Store", "type": "store", "address": "727 Northwest Loop 410, San Antonio, Texas 78216, USA", "lat": None, "lng": None},
    {"id": "121", "name": "Bulverde North Retail Store", "type": "store", "address": "20475 TX-46 Suite 108, Spring Branch, TX 78070", "lat": None, "lng": None},
    {"id": "159", "name": "Bulverde Retail Store", "type": "store", "address": "3730 North Loop 1604 East, San Antonio, Texas 78247, USA", "lat": None, "lng": None},
    {"id": "188", "name": "Cibolo Retail Store", "type": "store", "address": "635 Cibolo Valley Dr, Cibolo, Texas 78108, USA", "lat": None, "lng": None},
    {
        "id": "128",
        "name": "Commerce Retail Store",
        "type": "store",
        "address": "406 W Commerce St, San Antonio, Texas 78207, USA",
        "lat": None,
        "lng": None,
    },
    {"id": "157", "name": "Culebra Retail Store", "type": "store", "address": "10647 Culebra Rd, San Antonio, Texas 78251, USA", "lat": None, "lng": None},
    {"id": "152", "name": "DeZavala Retail Store", "type": "store", "address": "12332 Interstate 10, San Antonio, Texas 78230, USA", "lat": None, "lng": None},
    {"id": "120", "name": "Fredericksburg Retail Store", "type": "store", "address": "3401 Fredericksburg Rd, San Antonio, Texas 78201, USA", "lat": None, "lng": None},
    {"id": "158", "name": "Gateway Retail Store (Loop 1604)", "type": "store", "address": "7693 North Loop 1604 East, Live Oak, Texas 78233, USA", "lat": None, "lng": None},
    {"id": "155", "name": "Goliad Retail Store", "type": "store", "address": "2902 Goliad Rd, San Antonio, Texas 78223, USA", "lat": None, "lng": None},
    {"id": "160", "name": "Evans Retail Store", "type": "store", "address": "21230 Hwy 281, San Antonio, Texas 78258, USA", "lat": None, "lng": None},
    {"id": "186", "name": "Kerrville Retail Store", "type": "store", "address": "1048 Junction Hwy, Kerrville, Texas 78028, USA", "lat": None, "lng": None},
    {"id": "156", "name": "Laredo Retail Store", "type": "store", "address": "5901 San Dario Ave, Laredo, Texas 78041, USA", "lat": None, "lng": None},
    {"id": "145", "name": "Laredo Outlet Retail Store", "type": "outlet", "address": "11914 Conly Rd, Laredo, Texas 78045, USA", "lat": None, "lng": None},
    {"id": "127", "name": "Marbach Retail Store", "type": "store", "address": "1739 Southwest Loop 410, San Antonio, Texas 78227, USA", "lat": None, "lng": None},
    {"id": "151", "name": "New Braunfels Retail Store", "type": "store", "address": "1075 S Walnut Ave, New Braunfels, Texas 78130, USA", "lat": None, "lng": None},
    {"id": "183", "name": "Potranco Rd Retail Store", "type": "store", "address": "10422 Potranco Rd, San Antonio, Texas 78251, USA", "lat": None, "lng": None},
    {"id": "115", "name": "SA Outlet Retail Store", "type": "outlet", "address": "7702 I-35, Windcrest, Texas 78218, USA", "lat": None, "lng": None},
    {"id": "126", "name": "Seguin Retail Store", "type": "store", "address": "1431 E Court St, Seguin, Texas 78155, USA", "lat": None, "lng": None},
    {"id": "153", "name": "South Park Retail Store", "type": "store", "address": "2514 SW Military Dr, San Antonio, Texas 78224, USA", "lat": None, "lng": None},
    {"id": "129", "name": "Summit Retail Store", "type": "store", "address": "4949 Northwest Loop 410, San Antonio, Texas 78229, USA", "lat": None, "lng": None},
    {"id": "184", "name": "WW White Retail Store", "type": "store", "address": "1721 WW White Rd, SA, TX 78220", "lat": None, "lng": None},
    {"id": "124", "name": "Laredo Central Retail Store", "type": "store", "address": "1119 Guadalupe St, Laredo, TX 78040", "lat": None, "lng": None},
    {"id": "123", "name": "Lytle Retail Store", "type": "store", "address": "19585 I-35, Lytle, TX 78052", "lat": None, "lng": None},
    {"id": "119", "name": "Rittiman Retail Store", "type": "store", "address": "6363 Rittiman Rd, San Antonio, TX 78218", "lat": None, "lng": None},
]


def get_locations_static() -> List[Dict[str, Any]]:
    """Shape expected by GET /api/locations (matches DB column names)."""
    out = []
    for row in _RAW:
        out.append(
            {
                "LocationID": row["id"],
                "LocationName": row["name"],
                "LocationType": row["type"],
                "Manager": None,
                "Address": row.get("address"),
                "Latitude": row.get("lat"),
                "Longitude": row.get("lng"),
                "IsActive": True,
            }
        )
    return out


def get_pcounter_location_ids_for_store(store_id: str) -> List[int]:
    """
    PeopleCounter.dbo.PCounter numeric LocationID values for this app store.
    List multiple IDs when the site has separate sensors (e.g. Left + Right) to sum daily In counts.
    """
    meta = get_static_store_meta(store_id)
    if not meta:
        return []
    raw = meta.get("pcounter_location_ids")
    if raw is not None:
        return [int(x) for x in raw]
    one = meta.get("pcounter_location_id")
    if one is not None:
        return [int(one)]
    return []


def get_static_store_meta(store_id: str) -> Optional[Dict[str, Any]]:
    """Metadata for MTD sales filter; None if unknown id."""
    sid = (store_id or "").strip()
    for row in _RAW:
        if row["id"] == sid:
            return row
    return None


def sales_unit_name_for_store(store_id: str) -> Optional[str]:
    """GP [sales unit name] value: explicit sales_unit_name, else display name."""
    meta = get_static_store_meta(store_id)
    if not meta:
        return None
    su = meta.get("sales_unit_name")
    if su is not None and str(su).strip():
        return str(su).strip()
    return str(meta["name"]).strip()
