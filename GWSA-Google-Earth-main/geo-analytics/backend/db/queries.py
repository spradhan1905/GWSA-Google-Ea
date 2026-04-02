"""
GWSA GeoAnalytics — Parameterized SQL Queries
NEVER use string concatenation for values. Always use ? placeholders.
Table/view names come from Config (env) and are validated before use in SQL text.
"""
from db.connection import get_connection
from config import Config
from datetime import date, datetime, timedelta
from typing import Optional, Tuple
import decimal
import json
import re


def _validated_this_month_revenue_object() -> str:
    """This Month MTD: JS_API.dbo.TotalCoreTableFinal (or env override)."""
    name = (Config.SQL_THIS_MONTH_REVENUE_OBJECT or "").strip()
    if not name or not re.fullmatch(r"[A-Za-z0-9_\[\].]+", name):
        raise ValueError(
            "SQL_THIS_MONTH_REVENUE_OBJECT must be set (e.g. JS_API.dbo.TotalCoreTableFinal)"
        )
    return name


def _validated_retail_monthly_financial_object() -> str:
    """Quarter / YTD / 12 Months: JS_API.dbo.RetailStoreMonthlyFinancialSummary (or env override)."""
    name = (Config.SQL_RETAIL_MONTHLY_FINANCIAL_OBJECT or "").strip()
    if not name or not re.fullmatch(r"[A-Za-z0-9_\[\].]+", name):
        raise ValueError(
            "SQL_RETAIL_MONTHLY_FINANCIAL_OBJECT must be set "
            "(e.g. JS_API.dbo.RetailStoreMonthlyFinancialSummary)"
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

# TotalCoreTableFinal: daily [Date], [Revenue], [Unit] like 20-10-129-12000 (3rd hyphen segment = location id).
# Do NOT use PARSENAME: it only matches 4-part codes; 3-part Units would map the wrong segment.
TOTAL_CORE_DATE_SQL = "CAST(d.[Date] AS DATE)"
TOTAL_CORE_UNIT_LOCATION_ID_SQL = (
    "TRY_CAST(NULLIF(LTRIM(RTRIM(CAST("
    "N'<r><s>' + REPLACE(REPLACE(REPLACE(REPLACE("
    "LTRIM(RTRIM(CAST(d.[Unit] AS NVARCHAR(200)))), N'&', N'&amp;'), N'<', N'&lt;'), N'>', N'&gt;'), "
    "N'-', N'</s><s>') + N'</s></r>' AS XML).value('(/r/s)[3]', 'nvarchar(50)'))), N'') AS INT)"
)


def _total_core_category_filter_sql() -> Tuple[str, tuple]:
    """TotalCoreTableFinal: filter on [Category] OR [RevenueType] (e.g. Core Sales). Empty = no filter."""
    c = (Config.SQL_SALES_CORE_CATEGORY or "").strip()
    if not c:
        return "", ()
    frag = (
        " AND ( "
        " LTRIM(RTRIM(CAST(d.[Category] AS NVARCHAR(200)))) COLLATE Latin1_General_CI_AI "
        "= LTRIM(RTRIM(?)) COLLATE Latin1_General_CI_AI "
        " OR LTRIM(RTRIM(CAST(d.[RevenueType] AS NVARCHAR(200)))) COLLATE Latin1_General_CI_AI "
        "= LTRIM(RTRIM(?)) COLLATE Latin1_General_CI_AI "
        ")"
    )
    return frag, (c, c)


def _retail_unit_name_predicate_sql(unit: str) -> Tuple[str, tuple]:
    """Match RetailStoreMonthlyFinancialSummary.[Unit Name] to app store label."""
    u = (unit or "").strip()
    if not u:
        return " AND 1 = 0", ()
    col = "d.[Unit Name]"
    if Config.SQL_SALES_UNIT_NAME_FLEXIBLE:
        return (
            " AND ( "
            f" LTRIM(RTRIM(CAST({col} AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI "
            " = LTRIM(RTRIM(?)) COLLATE Latin1_General_CI_AI "
            " OR LTRIM(RTRIM(?)) COLLATE Latin1_General_CI_AI LIKE "
            f" N'%' + LTRIM(RTRIM(CAST({col} AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI + N'%' "
            f" OR LTRIM(RTRIM(CAST({col} AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI LIKE "
            " N'%' + LTRIM(RTRIM(?)) COLLATE Latin1_General_CI_AI + N'%' "
            ")",
            (u, u, u),
        )
    return (
        f" AND LTRIM(RTRIM(CAST({col} AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI "
        "= LTRIM(RTRIM(?)) COLLATE Latin1_General_CI_AI",
        (u,),
    )


def _retail_location_name_join_sql() -> str:
    """JOIN predicate: [Unit Name] to loc.LocationName (same rules as sales unit name)."""
    col = "d.[Unit Name]"
    if Config.SQL_SALES_UNIT_NAME_FLEXIBLE:
        return f"""
         AND (
              LTRIM(RTRIM(CAST({col} AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI
              = LTRIM(RTRIM(loc.LocationName)) COLLATE Latin1_General_CI_AI
           OR LTRIM(RTRIM(loc.LocationName)) COLLATE Latin1_General_CI_AI LIKE
              N'%' + LTRIM(RTRIM(CAST({col} AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI + N'%'
           OR LTRIM(RTRIM(CAST({col} AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI LIKE
              N'%' + LTRIM(RTRIM(loc.LocationName)) COLLATE Latin1_General_CI_AI + N'%'
         )"""
    return f"""
         AND LTRIM(RTRIM(CAST({col} AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI
              = LTRIM(RTRIM(loc.LocationName)) COLLATE Latin1_General_CI_AI"""


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
    If this_month is True: daily Core Sales revenue from TotalCoreTableFinal.
    Otherwise: monthly rollup from RetailStoreMonthlyFinancialSummary (Quarter / YTD / 12 Months / Custom),
    matched by [Unit Name] to static LocationName or dbo.Locations.LocationName.
    """
    if this_month:
        return _get_financials_this_month_sales(store_id, start_date, end_date)
    return _get_financials_retail_monthly(store_id, start_date, end_date)


def _total_core_join_pred_database() -> str:
    """Match TotalCore [Unit] location id to loc.LocationID / SoldStoreId, or [sales unit name] to LocationName."""
    uid = TOTAL_CORE_UNIT_LOCATION_ID_SQL
    if Config.SQL_SALES_UNIT_NAME_FLEXIBLE:
        return f"""
         AND (
              {uid} = TRY_CAST(loc.LocationID AS INT)
           OR (
                loc.SoldStoreId IS NOT NULL
                AND {uid} = loc.SoldStoreId
              )
           OR (
              LTRIM(RTRIM(CAST(d.[sales unit name] AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI
              = LTRIM(RTRIM(loc.LocationName)) COLLATE Latin1_General_CI_AI
           OR LTRIM(RTRIM(loc.LocationName)) COLLATE Latin1_General_CI_AI LIKE
              N'%' + LTRIM(RTRIM(CAST(d.[sales unit name] AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI + N'%'
           OR LTRIM(RTRIM(CAST(d.[sales unit name] AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI LIKE
              N'%' + LTRIM(RTRIM(loc.LocationName)) COLLATE Latin1_General_CI_AI + N'%'
         )"""
    return f"""
         AND (
              {uid} = TRY_CAST(loc.LocationID AS INT)
           OR (
                loc.SoldStoreId IS NOT NULL
                AND {uid} = loc.SoldStoreId
              )
           OR (
              LTRIM(RTRIM(CAST(d.[sales unit name] AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI
              = LTRIM(RTRIM(loc.LocationName)) COLLATE Latin1_General_CI_AI
         )"""


def _get_financials_this_month_sales(store_id: str, start_date: str, end_date: str) -> list:
    """
    SUM(Revenue) per day from TotalCoreTableFinal ([Date], [Revenue], [Unit], [Category], [sales unit name]).
    [Unit] uses hyphenated codes; location id is the 3rd segment (e.g. 20-10-129-12000 → 129).

    Static mode: filter by keys in db/static_locations.py (no dbo.Locations join).
    Database mode: INNER JOIN dbo.Locations (see SQL_LOCATIONS_* env).
    """
    if Config.LOCATIONS_SOURCE == "static":
        return _get_financials_this_month_sales_static(store_id, start_date, end_date)

    obj = _validated_this_month_revenue_object()
    loc_tbl = _validated_locations_table()
    sid = (store_id or "").strip()
    cat_sql, cat_params = _total_core_category_filter_sql()
    join_pred = _total_core_join_pred_database()

    sql = f"""
        SELECT
            {TOTAL_CORE_DATE_SQL} AS SalesDate,
            CAST(SUM(ISNULL(CAST(d.[Revenue] AS DECIMAL(18, 4)), 0)) AS DECIMAL(18, 2)) AS NetRevenue
        FROM {obj} AS d
        INNER JOIN {loc_tbl} AS loc
          ON loc.LocationID = ?
        {join_pred}
        WHERE 1 = 1
        {cat_sql}
          AND {TOTAL_CORE_DATE_SQL} >= CAST(? AS DATE)
          AND {TOTAL_CORE_DATE_SQL} <= CAST(? AS DATE)
        GROUP BY {TOTAL_CORE_DATE_SQL}
        ORDER BY SalesDate
    """
    return _execute_query(sql, (sid, *cat_params, start_date, end_date))


def _get_financials_this_month_sales_static(store_id: str, start_date: str, end_date: str) -> list:
    """MTD rows from TotalCoreTableFinal filtered by static store keys (no dbo.Locations)."""
    from db.static_locations import get_static_store_meta, sales_unit_name_for_store

    meta = get_static_store_meta(store_id)
    if not meta:
        return []

    obj = _validated_this_month_revenue_object()
    cat_sql, cat_params = _total_core_category_filter_sql()
    sold = meta.get("sold_store_id")
    ssu = meta.get("sales_store_unit")
    uid = TOTAL_CORE_UNIT_LOCATION_ID_SQL

    sum_rev = (
        "CAST(SUM(ISNULL(CAST(d.[Revenue] AS DECIMAL(18, 4)), 0)) AS DECIMAL(18, 2)) AS NetRevenue"
    )

    if sold is not None:
        sql = f"""
            SELECT
                {TOTAL_CORE_DATE_SQL} AS SalesDate,
                {sum_rev}
            FROM {obj} AS d
            WHERE {uid} = ?
            {cat_sql}
              AND {TOTAL_CORE_DATE_SQL} >= CAST(? AS DATE)
              AND {TOTAL_CORE_DATE_SQL} <= CAST(? AS DATE)
            GROUP BY {TOTAL_CORE_DATE_SQL}
            ORDER BY SalesDate
        """
        return _execute_query(sql, (int(sold), *cat_params, start_date, end_date))

    sid = (store_id or "").strip()
    if sid.isdigit():
        sql = f"""
            SELECT
                {TOTAL_CORE_DATE_SQL} AS SalesDate,
                {sum_rev}
            FROM {obj} AS d
            WHERE {uid} = ?
            {cat_sql}
              AND {TOTAL_CORE_DATE_SQL} >= CAST(? AS DATE)
              AND {TOTAL_CORE_DATE_SQL} <= CAST(? AS DATE)
            GROUP BY {TOTAL_CORE_DATE_SQL}
            ORDER BY SalesDate
        """
        return _execute_query(sql, (int(sid), *cat_params, start_date, end_date))

    if ssu is not None and str(ssu).strip():
        ssu_s = str(ssu).strip()
        sql = f"""
            SELECT
                {TOTAL_CORE_DATE_SQL} AS SalesDate,
                {sum_rev}
            FROM {obj} AS d
            WHERE CHARINDEX(LTRIM(RTRIM(?)), LTRIM(RTRIM(CAST(d.[Unit] AS NVARCHAR(200))))) > 0
            {cat_sql}
              AND {TOTAL_CORE_DATE_SQL} >= CAST(? AS DATE)
              AND {TOTAL_CORE_DATE_SQL} <= CAST(? AS DATE)
            GROUP BY {TOTAL_CORE_DATE_SQL}
            ORDER BY SalesDate
        """
        return _execute_query(sql, (ssu_s, *cat_params, start_date, end_date))

    unit = sales_unit_name_for_store(store_id)
    if not unit:
        return []
    unit_sql, unit_params = _sales_unit_name_predicate_sql(unit)
    sql = f"""
        SELECT
            {TOTAL_CORE_DATE_SQL} AS SalesDate,
            {sum_rev}
        FROM {obj} AS d
        WHERE 1 = 1
        {cat_sql}
        {unit_sql}
          AND {TOTAL_CORE_DATE_SQL} >= CAST(? AS DATE)
          AND {TOTAL_CORE_DATE_SQL} <= CAST(? AS DATE)
        GROUP BY {TOTAL_CORE_DATE_SQL}
        ORDER BY SalesDate
    """
    return _execute_query(sql, (*cat_params, *unit_params, start_date, end_date))


def _retail_monthly_select_columns() -> str:
    """Shared SELECT body for RetailStoreMonthlyFinancialSummary (grouped by Year/Month)."""
    return """
        DATEFROMPARTS(d.[Year], d.[Month], 1) AS PeriodMonth,
        CAST(SUM(ISNULL(d.[Total Revenue], 0)) AS DECIMAL(18, 2)) AS TotalRevenue,
        CAST(SUM(ISNULL(d.[Total Revenue], 0)) AS DECIMAL(18, 2)) AS NetRevenue,
        CAST(SUM(ISNULL(d.[Total Operating Expenses], 0)) AS DECIMAL(18, 2)) AS TotalOperatingExpenses,
        CAST(SUM(ISNULL(d.[Total Personnel Expenses], 0)) AS DECIMAL(18, 2)) AS TotalPersonnelExpenses,
        CAST(
            SUM(ISNULL(d.[Total Operating Expenses], 0)) + SUM(ISNULL(d.[Total Personnel Expenses], 0))
            AS DECIMAL(18, 2)
        ) AS OperatingExpenses,
        CAST(SUM(ISNULL(d.[Net Income], 0)) AS DECIMAL(18, 2)) AS NetIncome,
        CAST(
            CASE WHEN SUM(ISNULL(d.[Total Revenue], 0)) > 0
                THEN (
                    SUM(ISNULL(d.[Total Operating Expenses], 0)) + SUM(ISNULL(d.[Total Personnel Expenses], 0))
                ) / NULLIF(CAST(SUM(ISNULL(d.[Total Revenue], 0)) AS DECIMAL(38, 10)), 0)
                ELSE NULL END
            AS DECIMAL(18, 4)
        ) AS ExpenseRatio
    """


def _get_financials_retail_monthly(store_id: str, start_date: str, end_date: str) -> list:
    """Monthly rows from RetailStoreMonthlyFinancialSummary for the requested calendar-month span."""
    obj = _validated_retail_monthly_financial_object()
    month_lo = (
        "DATEFROMPARTS(d.[Year], d.[Month], 1) >= "
        "DATEFROMPARTS(YEAR(CAST(? AS DATE)), MONTH(CAST(? AS DATE)), 1)"
    )
    month_hi = (
        "DATEFROMPARTS(d.[Year], d.[Month], 1) <= "
        "DATEFROMPARTS(YEAR(CAST(? AS DATE)), MONTH(CAST(? AS DATE)), 1)"
    )
    month_params = (start_date, start_date, end_date, end_date)
    cols = _retail_monthly_select_columns()

    if Config.LOCATIONS_SOURCE == "static":
        from db.static_locations import get_static_store_meta, sales_unit_name_for_store

        meta = get_static_store_meta(store_id)
        if not meta:
            return []
        unit = sales_unit_name_for_store(store_id)
        if not unit:
            return []
        unit_sql, unit_params = _retail_unit_name_predicate_sql(unit)
        sql = f"""
            SELECT
                {cols}
            FROM {obj} AS d
            WHERE {month_lo}
              AND {month_hi}
            {unit_sql}
            GROUP BY d.[Year], d.[Month]
            ORDER BY d.[Year], d.[Month]
        """
        return _execute_query(sql, (*month_params, *unit_params))

    loc_tbl = _validated_locations_table()
    sid = (store_id or "").strip()
    join_name = _retail_location_name_join_sql()
    sql = f"""
        SELECT
            {cols}
        FROM {obj} AS d
        INNER JOIN {loc_tbl} AS loc
          ON loc.LocationID = ?
        {join_name}
        WHERE {month_lo}
          AND {month_hi}
        GROUP BY d.[Year], d.[Month]
        ORDER BY d.[Year], d.[Month]
    """
    return _execute_query(sql, (sid, *month_params))


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
    """Trend tab: monthly rollup from RetailStoreMonthlyFinancialSummary + door counts."""
    ids = _resolve_pcounter_location_ids(store_id)
    tbl = _validated_door_count_object()
    dcol = _bracketed_col(Config.SQL_DOOR_COUNT_COL_DATE, "SQL_DOOR_COUNT_COL_DATE")
    vcol = _bracketed_col(Config.SQL_DOOR_COUNT_COL_VISITS, "SQL_DOOR_COUNT_COL_VISITS")
    lcol = _bracketed_col(Config.SQL_DOOR_COUNT_COL_LOCATION, "SQL_DOOR_COUNT_COL_LOCATION")
    obj = _validated_retail_monthly_financial_object()

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
        ) dc ON agg.PeriodMonth = dc.MonthStart
        """
        door_params = tuple(ids)
    else:
        door_join = """
        LEFT JOIN (
            SELECT CAST(NULL AS DATE) AS MonthStart, CAST(0 AS INT) AS TotalVisits WHERE 1 = 0
        ) dc ON agg.PeriodMonth = dc.MonthStart
        """
        door_params = ()

    agg_select = """
                DATEFROMPARTS(d.[Year], d.[Month], 1) AS PeriodMonth,
                CAST(SUM(ISNULL(d.[Total Revenue], 0)) AS DECIMAL(18, 2)) AS NetRevenue,
                CAST(SUM(ISNULL(d.[Net Income], 0)) AS DECIMAL(18, 2)) AS NetIncome,
                CAST(
                    CASE WHEN SUM(ISNULL(d.[Total Revenue], 0)) > 0
                        THEN (
                            SUM(ISNULL(d.[Total Operating Expenses], 0))
                            + SUM(ISNULL(d.[Total Personnel Expenses], 0))
                        ) / NULLIF(CAST(SUM(ISNULL(d.[Total Revenue], 0)) AS DECIMAL(38, 10)), 0)
                        ELSE NULL END
                    AS DECIMAL(18, 4)
                ) AS ExpenseRatio
    """

    month_cutoff = (
        "DATEFROMPARTS(d.[Year], d.[Month], 1) >= DATEADD(MONTH, -?, GETDATE())"
    )

    if Config.LOCATIONS_SOURCE == "static":
        from db.static_locations import get_static_store_meta, sales_unit_name_for_store

        meta = get_static_store_meta(store_id)
        if not meta:
            return []
        unit = sales_unit_name_for_store(store_id)
        if not unit:
            return []
        unit_sql, unit_params = _retail_unit_name_predicate_sql(unit)
        sql = f"""
            SELECT
                agg.PeriodMonth,
                agg.NetRevenue,
                agg.NetIncome,
                agg.ExpenseRatio,
                CAST(0 AS DECIMAL(18, 2)) AS DonatedGoodsRev,
                CAST(0 AS DECIMAL(18, 2)) AS RetailRevenue,
                ISNULL(dc.TotalVisits, 0) AS DoorCount
            FROM (
                SELECT
                    {agg_select}
                FROM {obj} AS d
                WHERE {month_cutoff}
                {unit_sql}
                GROUP BY d.[Year], d.[Month]
            ) AS agg
            {door_join}
            ORDER BY agg.PeriodMonth
        """
        return _execute_query(sql, (months, *unit_params) + door_params)

    loc_tbl = _validated_locations_table()
    sid = (store_id or "").strip()
    join_name = _retail_location_name_join_sql()
    sql = f"""
        SELECT
            agg.PeriodMonth,
            agg.NetRevenue,
            agg.NetIncome,
            agg.ExpenseRatio,
            CAST(0 AS DECIMAL(18, 2)) AS DonatedGoodsRev,
            CAST(0 AS DECIMAL(18, 2)) AS RetailRevenue,
            ISNULL(dc.TotalVisits, 0) AS DoorCount
        FROM (
            SELECT
                {agg_select}
            FROM {obj} AS d
            INNER JOIN {loc_tbl} AS loc
              ON loc.LocationID = ?
            {join_name}
            WHERE {month_cutoff}
            GROUP BY d.[Year], d.[Month]
        ) AS agg
        {door_join}
        ORDER BY agg.PeriodMonth
    """
    return _execute_query(sql, (sid, months) + door_params)


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


def _coerce_number(value) -> float:
    """Normalize DB numeric values to plain float for chat summaries."""
    if value is None:
        return 0.0
    if isinstance(value, decimal.Decimal):
        return float(value)
    return float(value)


def _month_start(day: Optional[date] = None) -> date:
    current = day or date.today()
    return current.replace(day=1)


def _sum_field(rows: list, field: str) -> float:
    return round(sum(_coerce_number(row.get(field)) for row in rows), 2)


def _average_field(rows: list, field: str) -> float:
    if not rows:
        return 0.0
    return round(_sum_field(rows, field) / len(rows), 2)


def resolve_location_reference(reference: str) -> Optional[dict]:
    """Resolve a store by id or fuzzy name match against approved locations."""
    ref = (reference or "").strip().lower()
    if not ref:
        return None

    locations = get_locations()

    for loc in locations:
        if str(loc.get("LocationID", "")).strip().lower() == ref:
            return loc

    exact_name_matches = [
        loc for loc in locations
        if str(loc.get("LocationName", "")).strip().lower() == ref
    ]
    if exact_name_matches:
        return exact_name_matches[0]

    contains_matches = [
        loc for loc in locations
        if ref in str(loc.get("LocationName", "")).strip().lower()
    ]
    if len(contains_matches) == 1:
        return contains_matches[0]

    return None


def get_location_catalog(limit: int = 100) -> list:
    """Compact location list for AI intent planning."""
    catalog = []
    for loc in get_locations()[:limit]:
        catalog.append({
            "id": str(loc.get("LocationID")),
            "name": loc.get("LocationName"),
            "type": loc.get("LocationType"),
        })
    return catalog


def get_location_summary(store_id: str, today: Optional[date] = None) -> dict:
    """Approved store summary used by chat instead of free-form SQL."""
    current_day = today or date.today()
    start_of_month = _month_start(current_day)
    last_30_days = current_day - timedelta(days=29)
    location = resolve_location_reference(store_id)
    if not location:
        return {}

    financial_rows = get_financials(
        str(location["LocationID"]),
        start_of_month.isoformat(),
        current_day.isoformat(),
        this_month=True,
    )
    door_rows = get_door_count(
        str(location["LocationID"]),
        last_30_days.isoformat(),
        current_day.isoformat(),
    )

    summary = {
        "location_id": str(location["LocationID"]),
        "location_name": location.get("LocationName"),
        "location_type": location.get("LocationType"),
        "timeframes": {
            "revenue_start": start_of_month.isoformat(),
            "revenue_end": current_day.isoformat(),
            "door_count_start": last_30_days.isoformat(),
            "door_count_end": current_day.isoformat(),
        },
        "metrics": {
            "this_month_revenue": _sum_field(financial_rows, "NetRevenue"),
            "last_30_days_door_count": int(round(_sum_field(door_rows, "DonorVisits"))),
            "avg_daily_door_count_30d": _average_field(door_rows, "DonorVisits"),
        },
    }

    trend_rows = get_trends(str(location["LocationID"]), 12)
    summary["metrics"]["latest_month_revenue"] = (
        _coerce_number(trend_rows[-1].get("NetRevenue")) if trend_rows else 0.0
    )
    summary["metrics"]["latest_month_door_count"] = (
        int(round(_coerce_number(trend_rows[-1].get("DoorCount")))) if trend_rows else 0
    )
    return summary


def compare_locations(metric: str, store_refs: list, today: Optional[date] = None) -> dict:
    """Compare approved metrics across up to two locations."""
    current_day = today or date.today()
    resolved = []
    for ref in store_refs[:2]:
        loc = resolve_location_reference(ref)
        if loc and all(str(existing["LocationID"]) != str(loc["LocationID"]) for existing in resolved):
            resolved.append(loc)

    if len(resolved) < 2:
        return {"metric": metric, "locations": []}

    comparisons = []
    if metric == "door_count":
        start = (current_day - timedelta(days=29)).isoformat()
        end = current_day.isoformat()
        for loc in resolved:
            rows = get_door_count(str(loc["LocationID"]), start, end)
            comparisons.append({
                "location_id": str(loc["LocationID"]),
                "location_name": loc.get("LocationName"),
                "metric_value": int(round(_sum_field(rows, "DonorVisits"))),
            })
        timeframe = {"start": start, "end": end}
    else:
        start = _month_start(current_day).isoformat()
        end = current_day.isoformat()
        for loc in resolved:
            rows = get_financials(str(loc["LocationID"]), start, end, this_month=True)
            comparisons.append({
                "location_id": str(loc["LocationID"]),
                "location_name": loc.get("LocationName"),
                "metric_value": _sum_field(rows, "NetRevenue"),
            })
        timeframe = {"start": start, "end": end}

    ordered = sorted(comparisons, key=lambda item: item["metric_value"], reverse=True)
    return {
        "metric": metric,
        "timeframe": timeframe,
        "locations": comparisons,
        "leader": ordered[0] if ordered else None,
    }


def rank_locations(metric: str, limit: int = 5, today: Optional[date] = None) -> dict:
    """Rank locations by an approved metric using parameterized queries only."""
    current_day = today or date.today()
    locations = get_locations()
    rows = []

    if metric == "door_count":
        start = (current_day - timedelta(days=29)).isoformat()
        end = current_day.isoformat()
        for loc in locations:
            counts = get_door_count(str(loc["LocationID"]), start, end)
            rows.append({
                "location_id": str(loc["LocationID"]),
                "location_name": loc.get("LocationName"),
                "metric_value": int(round(_sum_field(counts, "DonorVisits"))),
            })
    else:
        start = _month_start(current_day).isoformat()
        end = current_day.isoformat()
        for loc in locations:
            financials = get_financials(str(loc["LocationID"]), start, end, this_month=True)
            rows.append({
                "location_id": str(loc["LocationID"]),
                "location_name": loc.get("LocationName"),
                "metric_value": _sum_field(financials, "NetRevenue"),
            })

    ranked = sorted(rows, key=lambda item: item["metric_value"], reverse=True)[:max(1, min(limit, 10))]
    return {
        "metric": metric,
        "timeframe": {"start": start, "end": end},
        "locations": ranked,
    }
