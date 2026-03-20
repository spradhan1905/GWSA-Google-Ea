"""
GWSA GeoAnalytics — Mock Data for Demo Mode
Realistic sample data when SQL Server is unavailable.
"""
import random
from datetime import date, timedelta


MOCK_LOCATIONS = [
    {"LocationID": "loc-01", "LocationName": "Bandera Landing II Donation Station", "LocationType": "adc", "Manager": None, "Address": "8010 Bandera Rd, San Antonio, Texas, 78250", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-02", "LocationName": "Churchill Estates Donation Station", "LocationType": "adc", "Manager": None, "Address": "15502 Huebner Rd, San Antonio, Texas, 78248", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-03", "LocationName": "Garden Ridge Donation Station", "LocationType": "adc", "Manager": None, "Address": "5580 FM 3009, Schertz, San Antonio, Texas, 78154", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-04", "LocationName": "Lakeside Plaza Donation Station", "LocationType": "adc", "Manager": None, "Address": "26212 Canyon Golf Rd, Suite 103, San Antonio, Texas, 78260", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-05", "LocationName": "Oak Park Donation Station", "LocationType": "adc", "Manager": None, "Address": "8001 N New Braunfels Ave, San Antonio, Texas, 78209", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-06", "LocationName": "SOHO Donation Station", "LocationType": "adc", "Manager": None, "Address": "19903 Stone Oak Pkwy, Suite 111, San Antonio, Texas, 78258", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-07", "LocationName": "Leon Springs Donation Station", "LocationType": "adc", "Manager": None, "Address": "24200 IH 10 West, Suite 103, San Antonio, Texas, 78257", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-08", "LocationName": "Austin Hwy Retail Store", "LocationType": "store", "Manager": None, "Address": "1533 Austin Highway, San Antonio, Texas 78218, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-09", "LocationName": "Bandera Retail Store", "LocationType": "store", "Manager": None, "Address": "11722 Quincy Lee Drive, San Antonio, Texas 78249, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-10", "LocationName": "Bitters Retail Store", "LocationType": "store", "Manager": None, "Address": "13311 San Pedro Avenue, San Antonio, TX, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-11", "LocationName": "Blanco North Retail Store", "LocationType": "store", "Manager": None, "Address": "18478 Blanco Rd, San Antonio, Texas 78258, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-12", "LocationName": "Blanco Retail Store", "LocationType": "store", "Manager": None, "Address": "727 Northwest Loop 410, San Antonio, Texas 78216, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-13", "LocationName": "Bulverde North Retail Store", "LocationType": "store", "Manager": None, "Address": "20475 TX-46 Suite 108, Spring Branch, TX 78070", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-14", "LocationName": "Bulverde Retail Store", "LocationType": "store", "Manager": None, "Address": "3730 North Loop 1604 East, San Antonio, Texas 78247, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-15", "LocationName": "Cibolo Retail Store", "LocationType": "store", "Manager": None, "Address": "635 Cibolo Valley Dr, Cibolo, Texas 78108, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-16", "LocationName": "Commerce Retail Store", "LocationType": "store", "Manager": None, "Address": "406 W Commerce St, San Antonio, Texas 78207, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-17", "LocationName": "Culebra Retail Store", "LocationType": "store", "Manager": None, "Address": "10647 Culebra Rd, San Antonio, Texas 78251, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-18", "LocationName": "DeZavala Retail Store", "LocationType": "store", "Manager": None, "Address": "12332 Interstate 10, San Antonio, Texas 78230, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-19", "LocationName": "Gateway Retail Store (Fredericksburg)", "LocationType": "store", "Manager": None, "Address": "3401 Fredericksburg Rd, San Antonio, Texas 78201, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-20", "LocationName": "Gateway Retail Store (Loop 1604)", "LocationType": "store", "Manager": None, "Address": "7693 North Loop 1604 East, Live Oak, Texas 78233, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-21", "LocationName": "Goliad Retail Store", "LocationType": "store", "Manager": None, "Address": "2902 Goliad Rd, San Antonio, Texas 78223, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-22", "LocationName": "Evans Retail Store", "LocationType": "store", "Manager": None, "Address": "21230 Hwy 281, San Antonio, Texas 78258, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-23", "LocationName": "Kerrville Retail Store", "LocationType": "store", "Manager": None, "Address": "1048 Junction Hwy, Kerrville, Texas 78028, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-24", "LocationName": "Laredo Retail Store", "LocationType": "store", "Manager": None, "Address": "5901 San Dario Ave, Laredo, Texas 78041, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-25", "LocationName": "Laredo Outlet Retail Store", "LocationType": "outlet", "Manager": None, "Address": "11914 Conly Rd, Laredo, Texas 78045, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-26", "LocationName": "Marbach Retail Store", "LocationType": "store", "Manager": None, "Address": "1739 Southwest Loop 410, San Antonio, Texas 78227, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-27", "LocationName": "New Braunfels Retail Store", "LocationType": "store", "Manager": None, "Address": "1075 S Walnut Ave, New Braunfels, Texas 78130, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-28", "LocationName": "Potranco Rd Retail Store", "LocationType": "store", "Manager": None, "Address": "10422 Potranco Rd, San Antonio, Texas 78251, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-29", "LocationName": "SA Outlet Retail Store", "LocationType": "outlet", "Manager": None, "Address": "7702 I-35, Windcrest, Texas 78218, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-30", "LocationName": "Seguin Retail Store", "LocationType": "store", "Manager": None, "Address": "1431 E Court St, Seguin, Texas 78155, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-31", "LocationName": "South Park Retail Store", "LocationType": "store", "Manager": None, "Address": "2514 SW Military Dr, San Antonio, Texas 78224, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-32", "LocationName": "Summit Retail Store", "LocationType": "store", "Manager": None, "Address": "4949 Northwest Loop 410, San Antonio, Texas 78229, USA", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-33", "LocationName": "WW White Retail Store", "LocationType": "store", "Manager": None, "Address": "1721 WW White Rd, SA, TX 78220", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-34", "LocationName": "Laredo Central Retail Store", "LocationType": "store", "Manager": None, "Address": "1119 Guadalupe St, Laredo, TX 78040", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-35", "LocationName": "Lytle Retail Store", "LocationType": "store", "Manager": None, "Address": "19585 I-35, Lytle, TX 78052", "Latitude": None, "Longitude": None, "IsActive": True},
    {"LocationID": "loc-36", "LocationName": "Rittiman Retail Store", "LocationType": "store", "Manager": None, "Address": "6363 Rittiman Rd, San Antonio, TX 78218", "Latitude": None, "Longitude": None, "IsActive": True},
]


def _gen_financial_row(month_date, base_rev=None):
    """Generate a single financial row with realistic variance."""
    base = base_rev or random.uniform(80000, 250000)
    net_rev = round(base + random.uniform(-15000, 15000), 2)
    expense_ratio = round(random.uniform(0.55, 0.82), 4)
    net_income = round(net_rev * (1 - expense_ratio), 2)
    donated = round(net_rev * random.uniform(0.25, 0.45), 2)
    retail = round(net_rev - donated, 2)
    return {
        "PeriodMonth": month_date.isoformat(),
        "NetRevenue": net_rev,
        "NetIncome": net_income,
        "ExpenseRatio": expense_ratio,
        "DonatedGoodsRev": donated,
        "RetailRevenue": retail,
    }


def get_mock_financials(store_id: str, start: str, end: str) -> list:
    """Generate mock financial data for a date range."""
    random.seed(hash(store_id) % 1000)
    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end)
    base_rev = random.uniform(80000, 250000)
    results = []
    current = date(start_d.year, start_d.month, 1)
    while current <= end_d:
        results.append(_gen_financial_row(current, base_rev))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return results


def get_mock_door_count(store_id: str, start: str, end: str) -> list:
    """Generate mock door count data for a date range."""
    random.seed(hash(store_id) % 1000 + 42)
    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end)
    results = []
    current = start_d
    while current <= end_d:
        if current.weekday() < 7:  # all days
            visits = random.randint(30, 180)
            # weekends are busier
            if current.weekday() >= 5:
                visits = random.randint(100, 250)
            results.append({
                "CountDate": current.isoformat(),
                "DonorVisits": visits,
            })
        current += timedelta(days=1)
    return results


def get_mock_trends(store_id: str, months: int = 12) -> list:
    """Generate mock trend data."""
    random.seed(hash(store_id) % 1000 + 99)
    results = []
    today = date.today()
    for i in range(months, 0, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        month_date = date(y, m, 1)
        fin = _gen_financial_row(month_date)
        fin["DoorCount"] = random.randint(800, 4500)
        results.append(fin)
    return results


def get_mock_donor_addresses(store_id: str) -> list:
    """Generate mock donor addresses around a store for Donor Map tab."""
    # Get store coords from MOCK_LOCATIONS
    loc = next((l for l in MOCK_LOCATIONS if l["LocationID"] == store_id), None)
    if not loc:
        return []
    lat_val, lng_val = loc.get("Latitude"), loc.get("Longitude")
    if lat_val is None or lng_val is None:
        return []
    lat, lng = float(lat_val), float(lng_val)
    random.seed(hash(store_id) % 1000 + 200)
    results = []
    for i in range(12):
        results.append({
            "DonorID": i + 1,
            "LocationID": store_id,
            "Address1": f"{100 + i * 50} Mock St",
            "City": "San Antonio",
            "State": "TX",
            "Zip": "78201",
            "Latitude": round(lat + random.uniform(-0.04, 0.04), 6),
            "Longitude": round(lng + random.uniform(-0.04, 0.04), 6),
            "KmlLayer": "Donor Addresses",
        })
    return results
