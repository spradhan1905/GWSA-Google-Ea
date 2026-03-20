"""
GWSA GeoAnalytics — Parameterized SQL Queries
NEVER use string concatenation. Always use ? placeholders.
"""
from db.connection import get_connection
from datetime import date, timedelta
import decimal
import json


class DecimalEncoder(json.JSONEncoder):
    """Handle Decimal serialization."""
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        if isinstance(o, date):
            return o.isoformat()
        return super().default(o)


def _execute_query(sql: str, params: tuple) -> list:
    """Execute a parameterized query and return list of dicts."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        cols = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        result = []
        for row in rows:
            d = {}
            for i, col in enumerate(cols):
                val = row[i]
                if isinstance(val, decimal.Decimal):
                    d[col] = float(val)
                elif isinstance(val, date):
                    d[col] = val.isoformat()
                else:
                    d[col] = val
            result.append(d)
        return result
    finally:
        conn.close()


def get_locations() -> list:
    """Get all active locations."""
    sql = """
        SELECT LocationID, LocationName, LocationType, Manager,
               Latitude, Longitude, IsActive
        FROM dbo.Locations
        WHERE IsActive = 1
        ORDER BY LocationName
    """
    return _execute_query(sql, ())


def get_financials(store_id: str, start_date: str, end_date: str) -> list:
    """Get financial data for a location within a date range."""
    sql = """
        SELECT PeriodMonth, NetRevenue, NetIncome, ExpenseRatio,
               DonatedGoodsRev, RetailRevenue
        FROM dbo.Financials
        WHERE LocationID = ?
          AND PeriodMonth BETWEEN ? AND ?
        ORDER BY PeriodMonth
    """
    return _execute_query(sql, (store_id, start_date, end_date))


def get_door_count(store_id: str, start_date: str, end_date: str) -> list:
    """Get door count data for a location within a date range."""
    sql = """
        SELECT CountDate, DonorVisits
        FROM dbo.DoorCount
        WHERE LocationID = ?
          AND CountDate BETWEEN ? AND ?
        ORDER BY CountDate
    """
    return _execute_query(sql, (store_id, start_date, end_date))


def get_trends(store_id: str, months: int = 12) -> list:
    """Get trend data combining financials and door counts."""
    sql = """
        SELECT
            f.PeriodMonth,
            f.NetRevenue,
            f.NetIncome,
            f.ExpenseRatio,
            f.DonatedGoodsRev,
            f.RetailRevenue,
            ISNULL(dc.TotalVisits, 0) AS DoorCount
        FROM dbo.Financials f
        LEFT JOIN (
            SELECT LocationID,
                   DATEFROMPARTS(YEAR(CountDate), MONTH(CountDate), 1) AS MonthStart,
                   SUM(DonorVisits) AS TotalVisits
            FROM dbo.DoorCount
            WHERE LocationID = ?
            GROUP BY LocationID, DATEFROMPARTS(YEAR(CountDate), MONTH(CountDate), 1)
        ) dc ON f.LocationID = dc.LocationID AND f.PeriodMonth = dc.MonthStart
        WHERE f.LocationID = ?
          AND f.PeriodMonth >= DATEADD(MONTH, -?, GETDATE())
        ORDER BY f.PeriodMonth
    """
    return _execute_query(sql, (store_id, store_id, months))


def get_donor_addresses(store_id: str) -> list:
    """Get donor addresses (lat/lng) for a location's catchment area."""
    sql = """
        SELECT DonorID, LocationID, Address1, City, State, Zip,
               Latitude, Longitude, KmlLayer
        FROM dbo.DonorAddresses
        WHERE LocationID = ?
          AND Latitude IS NOT NULL
          AND Longitude IS NOT NULL
        ORDER BY DonorID
    """
    return _execute_query(sql, (store_id,))
