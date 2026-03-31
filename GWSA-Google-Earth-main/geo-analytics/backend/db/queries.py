"""
GWSA GeoAnalytics — Parameterized SQL Queries
NEVER use string concatenation for values. Always use ? placeholders.
Table/view names come from Config (env) and are validated before use in SQL text.
"""
from db.connection import get_connection
from config import Config
from datetime import date, datetime, timedelta
from typing import Tuple
import decimal
import json
import re


def _validated_sales_object() -> str:
    """Allow only safe identifier characters for dbo.MyTable or schema.dbo.MyView."""
    name = (Config.SQL_SALES_LINE_OBJECT or "").strip()
    if not name or not re.fullmatch(r"[A-Za-z0-9_\[\].]+", name):
        raise ValueError(
            "SQL_SALES_LINE_OBJECT must be set to your sales table/view "
            "(e.g. JS_API.dbo.vw_DailySales)"
        )
    return name


def _validated_locations_table() -> str:
    """Locations table (join key LocationID + display name for GP sales unit)."""
    name = (Config.SQL_LOCATIONS_TABLE or "").strip()
    if not name or not re.fullmatch(r"[A-Za-z0-9_\[\].]+", name):
        raise ValueError("SQL_LOCATIONS_TABLE must be like dbo.Locations or JS_API.dbo.Locations")
    return name


def _validated_door_count_object() -> str:
    """PeopleCounter.dbo.PCounter or other three-part table name."""
    name = (Config.SQL_DOOR_COUNT_OBJECT or "").strip()
    if not name or not re.fullmatch(r"[A-Za-z0-9_\[\].]+", name):
        raise ValueError(
            "SQL_DOOR_COUNT_OBJECT must be set (e.g. PeopleCounter.dbo.PCounter)"
        )
    return name


def _bracketed_col(name: str, label: str) -> str:
    """Single identifier [ColName] for SQL Server (no user input; from Config only)."""
    n = (name or "").strip()
    if not n or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", n):
        raise ValueError(f"Invalid {label}: {name!r} (use letters, digits, underscore)")
    return f"[{n}]"


def _resolve_pcounter_location_ids(store_id: str) -> list:
    """
    Numeric PCounter LocationID list for the app store (sum Left + Right when multiple).
    Static: pcounter_location_ids / pcounter_location_id on each store; else all-digit store_id as one ID.
    """
    if Config.LOCATIONS_SOURCE == "static":
        from db.static_locations import get_pcounter_location_ids_for_store
        ids = get_pcounter_location_ids_for_store(store_id)
        if ids:
            return ids
        s = (store_id or "").strip()
        if s.isdigit():
            return [int(s)]
        return []
    return _pcounter_location_ids_from_db(store_id)


def _pcounter_location_ids_from_db(store_id: str) -> list:
    """Optional: extend dbo.Locations with PCounterLocationID(s). Currently returns []."""
    return []


def _sales_category_filter_sql() -> Tuple[str, tuple]:
    """
    Optional filter on SalesCategoryFromGP (trim + case-insensitive).
    If SQL_SALES_CORE_CATEGORY is empty in .env, no filter (sums all revenue lines for the store).
    """
    c = (Config.SQL_SALES_CORE_CATEGORY or "").strip()
    if not c:
        return "", ()
    frag = (
        " AND LTRIM(RTRIM(CAST(d.SalesCategoryFromGP AS NVARCHAR(200)))) COLLATE Latin1_General_CI_AI "
        "= LTRIM(RTRIM(?)) COLLATE Latin1_General_CI_AI"
    )
    return frag, (c,)


# Soldts may be DATETIME2 or Excel-style serial float (see sample_sales_file.xlsx). Plain CAST(... AS DATE) is NULL for float.
SOLDTS_AS_DATE_SQL = "CAST(TRY_CONVERT(DATETIME, d.Soldts) AS DATE)"


def _sales_unit_name_predicate_sql(unit: str) -> Tuple[str, tuple]:
    """Match [sales unit name] to app/GP store label; flexible = substring either way."""
    u = (unit or "").strip()
    if not u:
        return " AND 1 = 0", ()
    if Config.SQL_SALES_UNIT_NAME_FLEXIBLE:
        return (
            " AND ( "
            " LTRIM(RTRIM(CAST(d.[sales unit name] AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI "
            " = LTRIM(RTRIM(?)) COLLATE Latin1_General_CI_AI "
            " OR LTRIM(RTRIM(?)) COLLATE Latin1_General_CI_AI LIKE "
            " N'%' + LTRIM(RTRIM(CAST(d.[sales unit name] AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI + N'%' "
            " OR LTRIM(RTRIM(CAST(d.[sales unit name] AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI LIKE "
            " N'%' + LTRIM(RTRIM(?)) COLLATE Latin1_General_CI_AI + N'%' "
            ")",
            (u, u, u),
        )
    return (
        " AND LTRIM(RTRIM(CAST(d.[sales unit name] AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI "
        "= LTRIM(RTRIM(?)) COLLATE Latin1_General_CI_AI",
        (u,),
    )


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
                elif isinstance(val, datetime):
                    d[col] = val.date().isoformat()
                elif isinstance(val, date):
                    d[col] = val.isoformat()
                else:
                    d[col] = val
            result.append(d)
        return result
    finally:
        conn.close()


def get_locations() -> list:
    """Get all active locations: static list or dbo.Locations in SQL."""
    if Config.LOCATIONS_SOURCE == "static":
        from db.static_locations import get_locations_static
        return get_locations_static()

    loc_tbl = _validated_locations_table()
    if Config.SQL_LOCATIONS_MINIMAL_JOIN:
        sql = f"""
            SELECT LocationID, LocationName, LocationType, Manager,
                   Latitude, Longitude, IsActive
            FROM {loc_tbl}
            WHERE IsActive = 1
            ORDER BY LocationName
        """
    else:
        sql = f"""
            SELECT LocationID, LocationName, LocationType, Manager,
                   Latitude, Longitude, IsActive,
                   SoldStoreId, SalesStoreUnit
            FROM {loc_tbl}
            WHERE IsActive = 1
            ORDER BY LocationName
        """
    return _execute_query(sql, ())


def get_financials(store_id: str, start_date: str, end_date: str, this_month: bool = False) -> list:
    """
    If this_month is True: Core Sales daily revenue from JS_API.dbo.SalesFactFinal (This Month UI).
    Otherwise: monthly rollup from dbo.Financials (Quarter / YTD / 12 Months presets).
    Static locations mode has no dbo.Financials — non–This-Month presets return no rows.
    """
    if this_month:
        return _get_financials_this_month_sales(store_id, start_date, end_date)
    if Config.LOCATIONS_SOURCE == "static":
        return []
    return _get_financials_legacy(store_id, start_date, end_date)


def _get_financials_this_month_sales(store_id: str, start_date: str, end_date: str) -> list:
    """
    SUM(Revenue) per day from SalesFactFinal (structure: sample_sales_file.xlsx).

    Static mode: filter by keys in db/static_locations.py (no dbo.Locations join).
    Database mode: INNER JOIN dbo.Locations (see SQL_LOCATIONS_* env).
    """
    if Config.LOCATIONS_SOURCE == "static":
        return _get_financials_this_month_sales_static(store_id, start_date, end_date)

    obj = _validated_sales_object()
    loc_tbl = _validated_locations_table()
    sid = (store_id or "").strip()
    cat_sql, cat_params = _sales_category_filter_sql()

    if Config.SQL_LOCATIONS_MINIMAL_JOIN:
        if Config.SQL_SALES_UNIT_NAME_FLEXIBLE:
            join_pred = """
         AND (
              LTRIM(RTRIM(CAST(d.[sales unit name] AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI
              = LTRIM(RTRIM(loc.LocationName)) COLLATE Latin1_General_CI_AI
           OR LTRIM(RTRIM(loc.LocationName)) COLLATE Latin1_General_CI_AI LIKE
              N'%' + LTRIM(RTRIM(CAST(d.[sales unit name] AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI + N'%'
           OR LTRIM(RTRIM(CAST(d.[sales unit name] AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI LIKE
              N'%' + LTRIM(RTRIM(loc.LocationName)) COLLATE Latin1_General_CI_AI + N'%'
           OR (
                TRY_CAST(loc.LocationID AS INT) IS NOT NULL
                AND d.SoldStoreId = TRY_CAST(loc.LocationID AS INT)
              )
         )"""
        else:
            join_pred = """
         AND (
              LTRIM(RTRIM(CAST(d.[sales unit name] AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI
              = LTRIM(RTRIM(loc.LocationName)) COLLATE Latin1_General_CI_AI
           OR (
                TRY_CAST(loc.LocationID AS INT) IS NOT NULL
                AND d.SoldStoreId = TRY_CAST(loc.LocationID AS INT)
              )
         )"""
    else:
        if Config.SQL_SALES_UNIT_NAME_FLEXIBLE:
            join_pred = """
         AND (
              (loc.SoldStoreId IS NOT NULL AND d.SoldStoreId = loc.SoldStoreId)
           OR (
                NULLIF(LTRIM(RTRIM(loc.SalesStoreUnit)), N'') IS NOT NULL
                AND LTRIM(RTRIM(CAST(d.[sales store unit] AS NVARCHAR(200)))) COLLATE Latin1_General_CI_AI
                 = LTRIM(RTRIM(loc.SalesStoreUnit)) COLLATE Latin1_General_CI_AI
              )
           OR LTRIM(RTRIM(CAST(d.[sales unit name] AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI
              = LTRIM(RTRIM(loc.LocationName)) COLLATE Latin1_General_CI_AI
           OR LTRIM(RTRIM(loc.LocationName)) COLLATE Latin1_General_CI_AI LIKE
              N'%' + LTRIM(RTRIM(CAST(d.[sales unit name] AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI + N'%'
           OR LTRIM(RTRIM(CAST(d.[sales unit name] AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI LIKE
              N'%' + LTRIM(RTRIM(loc.LocationName)) COLLATE Latin1_General_CI_AI + N'%'
           OR (
                TRY_CAST(loc.LocationID AS INT) IS NOT NULL
                AND d.SoldStoreId = TRY_CAST(loc.LocationID AS INT)
              )
         )"""
        else:
            join_pred = """
         AND (
              (loc.SoldStoreId IS NOT NULL AND d.SoldStoreId = loc.SoldStoreId)
           OR (
                NULLIF(LTRIM(RTRIM(loc.SalesStoreUnit)), N'') IS NOT NULL
                AND LTRIM(RTRIM(CAST(d.[sales store unit] AS NVARCHAR(200)))) COLLATE Latin1_General_CI_AI
                 = LTRIM(RTRIM(loc.SalesStoreUnit)) COLLATE Latin1_General_CI_AI
              )
           OR LTRIM(RTRIM(CAST(d.[sales unit name] AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI
              = LTRIM(RTRIM(loc.LocationName)) COLLATE Latin1_General_CI_AI
           OR (
                TRY_CAST(loc.LocationID AS INT) IS NOT NULL
                AND d.SoldStoreId = TRY_CAST(loc.LocationID AS INT)
              )
         )"""

    sql = f"""
        SELECT
            {SOLDTS_AS_DATE_SQL} AS SalesDate,
            CAST(SUM(ISNULL(CAST(d.Revenue AS DECIMAL(18, 4)), 0)) AS DECIMAL(18, 2)) AS NetRevenue
        FROM {obj} AS d
        INNER JOIN {loc_tbl} AS loc
          ON loc.LocationID = ?
        {join_pred}
        WHERE 1 = 1
        {cat_sql}
          AND {SOLDTS_AS_DATE_SQL} >= CAST(? AS DATE)
          AND {SOLDTS_AS_DATE_SQL} <= CAST(? AS DATE)
        GROUP BY {SOLDTS_AS_DATE_SQL}
        ORDER BY SalesDate
    """
    return _execute_query(sql, (sid, *cat_params, start_date, end_date))


def _get_financials_this_month_sales_static(store_id: str, start_date: str, end_date: str) -> list:
    """MTD rows from SalesFactFinal filtered by static store keys (no dbo.Locations)."""
    from db.static_locations import get_static_store_meta, sales_unit_name_for_store

    meta = get_static_store_meta(store_id)
    if not meta:
        return []

    obj = _validated_sales_object()
    cat_sql, cat_params = _sales_category_filter_sql()
    sold = meta.get("sold_store_id")
    ssu = meta.get("sales_store_unit")

    sum_rev = "CAST(SUM(ISNULL(CAST(d.Revenue AS DECIMAL(18, 4)), 0)) AS DECIMAL(18, 2)) AS NetRevenue"

    if sold is not None:
        sql = f"""
            SELECT
                {SOLDTS_AS_DATE_SQL} AS SalesDate,
                {sum_rev}
            FROM {obj} AS d
            WHERE d.SoldStoreId = ?
            {cat_sql}
              AND {SOLDTS_AS_DATE_SQL} >= CAST(? AS DATE)
              AND {SOLDTS_AS_DATE_SQL} <= CAST(? AS DATE)
            GROUP BY {SOLDTS_AS_DATE_SQL}
            ORDER BY SalesDate
        """
        return _execute_query(sql, (int(sold), *cat_params, start_date, end_date))

    if ssu is not None and str(ssu).strip():
        ssu_s = str(ssu).strip()
        sql = f"""
            SELECT
                {SOLDTS_AS_DATE_SQL} AS SalesDate,
                {sum_rev}
            FROM {obj} AS d
            WHERE LTRIM(RTRIM(CAST(d.[sales store unit] AS NVARCHAR(200)))) COLLATE Latin1_General_CI_AI
                  = LTRIM(RTRIM(?)) COLLATE Latin1_General_CI_AI
            {cat_sql}
              AND {SOLDTS_AS_DATE_SQL} >= CAST(? AS DATE)
              AND {SOLDTS_AS_DATE_SQL} <= CAST(? AS DATE)
            GROUP BY {SOLDTS_AS_DATE_SQL}
            ORDER BY SalesDate
        """
        return _execute_query(sql, (ssu_s, *cat_params, start_date, end_date))

    unit = sales_unit_name_for_store(store_id)
    if not unit:
        return []
    unit_sql, unit_params = _sales_unit_name_predicate_sql(unit)
    sql = f"""
        SELECT
            {SOLDTS_AS_DATE_SQL} AS SalesDate,
            {sum_rev}
        FROM {obj} AS d
        WHERE 1 = 1
        {cat_sql}
        {unit_sql}
          AND {SOLDTS_AS_DATE_SQL} >= CAST(? AS DATE)
          AND {SOLDTS_AS_DATE_SQL} <= CAST(? AS DATE)
        GROUP BY {SOLDTS_AS_DATE_SQL}
        ORDER BY SalesDate
    """
    return _execute_query(sql, (*cat_params, *unit_params, start_date, end_date))


def _get_financials_legacy(store_id: str, start_date: str, end_date: str) -> list:
    """Monthly financials from dbo.Financials (non–This Month presets)."""
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
    """
    Daily totals from PeopleCounter.dbo.PCounter: hourly rows rolled up to one row per calendar day,
    summing [In] across all sensors (e.g. Left + Right) via WHERE LocationID IN (...).
    """
    ids = _resolve_pcounter_location_ids(store_id)
    if not ids:
        return []
    tbl = _validated_door_count_object()
    dcol = _bracketed_col(Config.SQL_DOOR_COUNT_COL_DATE, "SQL_DOOR_COUNT_COL_DATE")
    vcol = _bracketed_col(Config.SQL_DOOR_COUNT_COL_VISITS, "SQL_DOOR_COUNT_COL_VISITS")
    lcol = _bracketed_col(Config.SQL_DOOR_COUNT_COL_LOCATION, "SQL_DOOR_COUNT_COL_LOCATION")
    ph = ",".join("?" * len(ids))
    sql = f"""
        SELECT CAST({dcol} AS DATE) AS CountDate, SUM({vcol}) AS DonorVisits
        FROM {tbl}
        WHERE {lcol} IN ({ph})
          AND CAST({dcol} AS DATE) BETWEEN ? AND ?
        GROUP BY CAST({dcol} AS DATE)
        ORDER BY CAST({dcol} AS DATE)
    """
    params = tuple(ids) + (start_date, end_date)
    return _execute_query(sql, params)


def get_trends(store_id: str, months: int = 12) -> list:
    """Trend tab: monthly rollup from dbo.Financials + door counts (not JS_API SalesFact)."""
    ids = _resolve_pcounter_location_ids(store_id)
    tbl = _validated_door_count_object()
    dcol = _bracketed_col(Config.SQL_DOOR_COUNT_COL_DATE, "SQL_DOOR_COUNT_COL_DATE")
    vcol = _bracketed_col(Config.SQL_DOOR_COUNT_COL_VISITS, "SQL_DOOR_COUNT_COL_VISITS")
    lcol = _bracketed_col(Config.SQL_DOOR_COUNT_COL_LOCATION, "SQL_DOOR_COUNT_COL_LOCATION")
    if ids:
        ph = ",".join("?" * len(ids))
        door_join = f"""
        LEFT JOIN (
            SELECT
                DATEFROMPARTS(YEAR(CountDate), MONTH(CountDate), 1) AS MonthStart,
                SUM(DonorVisits) AS TotalVisits
            FROM (
                SELECT CAST({dcol} AS DATE) AS CountDate, SUM({vcol}) AS DonorVisits
                FROM {tbl}
                WHERE {lcol} IN ({ph})
                GROUP BY CAST({dcol} AS DATE)
            ) d
            GROUP BY DATEFROMPARTS(YEAR(CountDate), MONTH(CountDate), 1)
        ) dc ON f.PeriodMonth = dc.MonthStart
        """
        door_params = tuple(ids)
    else:
        door_join = """
        LEFT JOIN (
            SELECT CAST(NULL AS DATE) AS MonthStart, CAST(0 AS INT) AS TotalVisits WHERE 1 = 0
        ) dc ON f.PeriodMonth = dc.MonthStart
        """
        door_params = ()
    sql = f"""
        SELECT
            f.PeriodMonth,
            f.NetRevenue,
            f.NetIncome,
            f.ExpenseRatio,
            f.DonatedGoodsRev,
            f.RetailRevenue,
            ISNULL(dc.TotalVisits, 0) AS DoorCount
        FROM dbo.Financials f
        {door_join}
        WHERE f.LocationID = ?
          AND f.PeriodMonth >= DATEADD(MONTH, -?, GETDATE())
        ORDER BY f.PeriodMonth
    """
    return _execute_query(sql, door_params + (store_id, months))


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
