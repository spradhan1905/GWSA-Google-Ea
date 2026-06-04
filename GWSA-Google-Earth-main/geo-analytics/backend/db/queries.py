"""
GWSA GeoAnalytics — Parameterized SQL Queries
NEVER use string concatenation for values. Always use ? placeholders.
Table/view names come from Config (env) and are validated before use in SQL text.
"""
from db.connection import acquire_pooled_connection, release_pooled_connection
from config import Config
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
import concurrent.futures
import decimal
import json
import math
import re

CONSOLIDATED_LOCATION_ID = "CONSOLIDATED"


def _is_consolidated_location(store_id: str) -> bool:
    return (store_id or "").strip().upper() == CONSOLIDATED_LOCATION_ID


def _validated_this_month_revenue_object() -> str:
    """This Month MTD: JS_API.dbo.TotalCoreTableFinal (or env override)."""
    name = (Config.SQL_THIS_MONTH_REVENUE_OBJECT or "").strip()
    if not name or not re.fullmatch(r"[A-Za-z0-9_\[\].]+", name):
        raise ValueError(
            "SQL_THIS_MONTH_REVENUE_OBJECT must be set (e.g. JS_API.dbo.TotalCoreTableFinal)"
        )
    return name


def _validated_sales_line_object() -> str:
    """Line-level POS: JS_API.dbo.SalesFactFinal (or env override)."""
    name = (Config.SQL_SALES_LINE_OBJECT or "").strip()
    if not name or not re.fullmatch(r"[A-Za-z0-9_\[\].]+", name):
        raise ValueError(
            "SQL_SALES_LINE_OBJECT must be set (e.g. JS_API.dbo.SalesFactFinal)"
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


def _validated_budget_vs_actual_object() -> str:
    """Actual vs Budget daily Core revenue: JS_API.dbo.DailyCoreRevenueBudgetVsActual_NoSubCategory (or env override)."""
    name = (Config.SQL_BUDGET_VS_ACTUAL_OBJECT or "").strip()
    if not name or not re.fullmatch(r"[A-Za-z0-9_\[\].]+", name):
        raise ValueError(
            "SQL_BUDGET_VS_ACTUAL_OBJECT must be set "
            "(e.g. JS_API.dbo.DailyCoreRevenueBudgetVsActual_NoSubCategory)"
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


def _hyphen_segment3_int_sql(unit_col_expr: str) -> str:
    """
    Extract the 3rd hyphen-delimited segment of a Unit code (e.g. 20-10-129-12000 -> 129) as INT,
    using cheap CHARINDEX/SUBSTRING string ops.

    Previously this used per-row XML construction + XQuery, which forced a full table scan with an
    expensive parse on every row (the main cause of multi-minute chat queries). Same value, far cheaper.
    """
    u = f"LTRIM(RTRIM(CAST({unit_col_expr} AS NVARCHAR(200))))"
    p1 = f"CHARINDEX('-',{u})"
    p2 = f"CHARINDEX('-',{u},{p1}+1)"
    p3 = f"CHARINDEX('-',{u},{p2}+1)"
    seg = f"SUBSTRING({u},{p2}+1,CASE WHEN {p3}>0 THEN {p3} ELSE LEN({u})+1 END-({p2}+1))"
    return f"TRY_CAST(NULLIF(LTRIM(RTRIM({seg})),N'') AS INT)"


TOTAL_CORE_UNIT_LOCATION_ID_SQL = _hyphen_segment3_int_sql("d.[Unit]")


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


def _rows_to_dicts(cursor) -> list:
    cols = [d[0] for d in cursor.description]
    result = []
    for row in cursor.fetchall():
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


def _execute_query(sql: str, params: tuple) -> list:
    """Execute a parameterized query against a pooled connection and return list of dicts.

    Borrows a warm connection from the pool. If the connection went stale (server closed
    an idle socket), it is discarded and the query retried once on a fresh connection.
    """
    last_exc = None
    for attempt in range(2):
        conn = acquire_pooled_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            result = _rows_to_dicts(cursor)
            cursor.close()
            release_pooled_connection(conn)
            return result
        except Exception as exc:
            # Drop the (possibly dead) connection from the pool, then retry once.
            release_pooled_connection(conn, broken=True)
            last_exc = exc
            if attempt == 0 and _is_retryable_db_error(exc):
                continue
            raise
    if last_exc:
        raise last_exc
    return []


def _is_retryable_db_error(exc: Exception) -> bool:
    """True for connection-level errors worth retrying on a fresh connection (not SQL syntax)."""
    msg = str(exc).lower()
    needles = (
        "communication link failure",
        "connection is busy",
        "connection was recovered",
        "connection reset",
        "broken pipe",
        "08s01",
        "08001",
        "10054",
        "timeout expired",
        "tcp provider",
        "general network error",
        "not connected",
    )
    return any(n in msg for n in needles)


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
    if this_month and _is_consolidated_location(store_id):
        return []
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

    if _is_consolidated_location(store_id):
        sql = f"""
            SELECT
                {cols}
            FROM {obj} AS d
            WHERE {month_lo}
              AND {month_hi}
            GROUP BY d.[Year], d.[Month]
            ORDER BY d.[Year], d.[Month]
        """
        return _execute_query(sql, month_params)

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


# DailyCoreRevenueBudgetVsActual_NoSubCategory: daily [Date], [Unit] (3rd segment = location id),
# [sales unit name], [Category], [ActualCoreRevenue], [BudgetCoreRevenue], [RevenueVariance].
BUDGET_DATE_SQL = "CAST(d.[Date] AS DATE)"
BUDGET_SUM_COLUMNS = """
        CAST(SUM(ISNULL(CAST(d.[ActualCoreRevenue] AS DECIMAL(18, 4)), 0)) AS DECIMAL(18, 2)) AS ActualRevenue,
        CAST(SUM(ISNULL(CAST(d.[BudgetCoreRevenue] AS DECIMAL(18, 4)), 0)) AS DECIMAL(18, 2)) AS BudgetRevenue,
        CAST(SUM(ISNULL(CAST(d.[RevenueVariance] AS DECIMAL(18, 4)), 0)) AS DECIMAL(18, 2)) AS RevenueVariance
"""


def _budget_category_filter_sql() -> Tuple[str, tuple]:
    """Budget table only has [Category] (no [RevenueType]). Empty SQL_SALES_CORE_CATEGORY = no filter."""
    c = (Config.SQL_SALES_CORE_CATEGORY or "").strip()
    if not c:
        return "", ()
    frag = (
        " AND LTRIM(RTRIM(CAST(d.[Category] AS NVARCHAR(200)))) COLLATE Latin1_General_CI_AI "
        "= LTRIM(RTRIM(?)) COLLATE Latin1_General_CI_AI"
    )
    return frag, (c,)


def _budget_period_grain_sql(grain: str) -> Tuple[str, str, str]:
    """(period_select, group_by, order_by) for daily or monthly buckets keyed as PeriodDate."""
    if (grain or "day").lower() == "month":
        return (
            "DATEFROMPARTS(d.[Year], d.[Month], 1) AS PeriodDate",
            "GROUP BY d.[Year], d.[Month]",
            "ORDER BY d.[Year], d.[Month]",
        )
    return (
        f"{BUDGET_DATE_SQL} AS PeriodDate",
        f"GROUP BY {BUDGET_DATE_SQL}",
        "ORDER BY PeriodDate",
    )


def _budget_unit_filter_static(store_id: str) -> Optional[Tuple[str, tuple]]:
    """
    WHERE fragment + params to scope the budget table to one app store (static mode).
    Mirrors the MTD TotalCore matching: [Unit] 3rd segment by sold/store id, then [sales unit name].
    Returns None when the store id is unknown.
    """
    from db.static_locations import get_static_store_meta, sales_unit_name_for_store

    meta = get_static_store_meta(store_id)
    if not meta:
        return None

    uid = TOTAL_CORE_UNIT_LOCATION_ID_SQL
    sold = meta.get("sold_store_id")
    ssu = meta.get("sales_store_unit")
    sid = (store_id or "").strip()

    if sold is not None:
        return f" AND {uid} = ?", (int(sold),)
    if sid.isdigit():
        return f" AND {uid} = ?", (int(sid),)
    if ssu is not None and str(ssu).strip():
        return (
            " AND CHARINDEX(LTRIM(RTRIM(?)), LTRIM(RTRIM(CAST(d.[Unit] AS NVARCHAR(200))))) > 0",
            (str(ssu).strip(),),
        )
    unit = sales_unit_name_for_store(store_id)
    if not unit:
        return None
    return _sales_unit_name_predicate_sql(unit)


def get_budget_vs_actual(store_id: str, start_date: str, end_date: str, grain: str = "day") -> list:
    """
    Actual vs Budget Core revenue from DailyCoreRevenueBudgetVsActual_NoSubCategory.
    grain='day'  -> one row per calendar day (This Month / Custom).
    grain='month' -> one row per Year/Month (Rolling 3 months / YTD / 12 Months) to avoid crowding.
    Each row: { PeriodDate, ActualRevenue, BudgetRevenue, RevenueVariance }.
    """
    obj = _validated_budget_vs_actual_object()
    cat_sql, cat_params = _budget_category_filter_sql()
    period_select, group_by, order_by = _budget_period_grain_sql(grain)

    date_filter = (
        f"{BUDGET_DATE_SQL} >= CAST(? AS DATE) AND {BUDGET_DATE_SQL} <= CAST(? AS DATE)"
    )

    # Consolidated: sum every unit (no store filter).
    if _is_consolidated_location(store_id):
        sql = f"""
            SELECT
                {period_select},
                {BUDGET_SUM_COLUMNS}
            FROM {obj} AS d
            WHERE {date_filter}
            {cat_sql}
            {group_by}
            {order_by}
        """
        return _execute_query(sql, (start_date, end_date, *cat_params))

    if Config.LOCATIONS_SOURCE == "static":
        unit_filter = _budget_unit_filter_static(store_id)
        if unit_filter is None:
            return []
        unit_sql, unit_params = unit_filter
        sql = f"""
            SELECT
                {period_select},
                {BUDGET_SUM_COLUMNS}
            FROM {obj} AS d
            WHERE {date_filter}
            {cat_sql}
            {unit_sql}
            {group_by}
            {order_by}
        """
        return _execute_query(sql, (start_date, end_date, *cat_params, *unit_params))

    # Database mode: INNER JOIN dbo.Locations using the same predicate as MTD TotalCore.
    loc_tbl = _validated_locations_table()
    sid = (store_id or "").strip()
    join_pred = _total_core_join_pred_database()
    sql = f"""
        SELECT
            {period_select},
            {BUDGET_SUM_COLUMNS}
        FROM {obj} AS d
        INNER JOIN {loc_tbl} AS loc
          ON loc.LocationID = ?
        {join_pred}
        WHERE {date_filter}
        {cat_sql}
        {group_by}
        {order_by}
    """
    return _execute_query(sql, (sid, start_date, end_date, *cat_params))


def _validated_donations_object() -> str:
    """Donations daily table: JS_API.dbo.tbl_Donation (or env override)."""
    name = (Config.SQL_DONATIONS_OBJECT or "").strip()
    if not name or not re.fullmatch(r"[A-Za-z0-9_\[\].]+", name):
        raise ValueError("SQL_DONATIONS_OBJECT must be set (e.g. JS_API.dbo.tbl_Donation)")
    return name


def _donations_effective_value_sql(alias: str = "d") -> str:
    """
    Per-row donation value: DonationAmt when present, else OverrideAmt, else NativeCount.
    Newer warehouse rows often populate NativeCount while DonationAmt stays 0.
    """
    acol = _bracketed_col(Config.SQL_DONATIONS_COL_AMOUNT, "SQL_DONATIONS_COL_AMOUNT")
    a = alias
    return f"""COALESCE(
        NULLIF(CAST({a}.{acol} AS DECIMAL(18, 4)), 0),
        NULLIF(CAST({a}.[OverrideAmt] AS DECIMAL(18, 4)), 0),
        CAST(ISNULL({a}.[NativeCount], 0) AS DECIMAL(18, 4))
    )"""


def _donations_sum_sql(alias: str = "d") -> str:
    """SUM of effective donation values for GROUP BY queries."""
    return (
        f"CAST(SUM({_donations_effective_value_sql(alias)}) AS DECIMAL(18, 2))"
    )


def _default_trend_daily_window(months: int) -> Tuple[str, str]:
    """Inclusive daily date span matching get_trends month window (through current month)."""
    months = max(1, int(months))
    today = date.today()
    end_month = date(today.year, today.month, 1)
    y, m = end_month.year, end_month.month - (months - 1)
    while m <= 0:
        m += 12
        y -= 1
    start_month = date(y, m, 1)
    if end_month.month == 12:
        end_daily = date(end_month.year, 12, 31)
    else:
        end_daily = date(end_month.year, end_month.month + 1, 1) - timedelta(days=1)
    return start_month.isoformat(), end_daily.isoformat()


def _resolve_trend_daily_window(
    months: int,
    start_date: Optional[str],
    end_date: Optional[str],
) -> Tuple[str, str]:
    if start_date and end_date:
        return start_date, end_date
    return _default_trend_daily_window(months)


def _validated_locations_detail_object() -> str:
    """Store metadata: JS_API.dbo.tbl_Locations (square footage, tier, etc.)."""
    name = (Config.SQL_LOCATIONS_DETAIL_OBJECT or "").strip()
    if not name or not re.fullmatch(r"[A-Za-z0-9_\[\].]+", name):
        raise ValueError("SQL_LOCATIONS_DETAIL_OBJECT must be set (e.g. JS_API.dbo.tbl_Locations)")
    return name


def get_location_detail(store_id: str) -> Optional[dict]:
    """One row from tbl_Locations for a store id (SalesSqrFt, Tier, etc.)."""
    sid = (store_id or "").strip()
    if not sid or _is_consolidated_location(sid):
        return None
    obj = _validated_locations_detail_object()
    sql = f"""
        SELECT TOP 1
            LocName,
            LocAdd,
            LocType,
            Storeid,
            Tier,
            TtlSqrFt,
            SalesSqrFt,
            ProdSqrFt,
            DateOpen,
            DateClosed
        FROM {obj}
        WHERE LTRIM(RTRIM(CAST(Storeid AS NVARCHAR(50)))) = LTRIM(RTRIM(?))
    """
    rows = _execute_query(sql, (sid,))
    return rows[0] if rows else None


def _ytd_window(as_of: str) -> tuple[str, str, int]:
    """Calendar YTD through as_of (inclusive day count)."""
    from datetime import date

    end = date.fromisoformat(as_of[:10])
    start = date(end.year, 1, 1)
    days = (end - start).days + 1
    return start.isoformat(), end.isoformat(), max(1, days)


def get_key_metrics(store_id: str, as_of: Optional[str] = None) -> dict:
    """
    Key Metrics tab: SalesSqrFt, annualized sales per sq ft, lease status.
    Sales per sq ft = ((YTD core sales / YTD days) / SalesSqrFt) * 365 (annualizedAvg).
    """
    from datetime import date
    from db.store_lease_status import lease_status_for_store

    sid = (store_id or "").strip()
    if not sid or _is_consolidated_location(sid):
        return {"error": "Key metrics are not available for this location."}

    as_of_iso = (as_of or date.today().isoformat())[:10]
    loc = get_location_detail(sid)
    ytd_start, ytd_end, ytd_days = _ytd_window(as_of_iso)
    daily = get_financials(sid, ytd_start, ytd_end, this_month=True)
    ytd_sales = sum(_coerce_number(r.get("NetRevenue")) for r in daily)

    sales_sqft = None
    if loc and loc.get("SalesSqrFt") is not None:
        try:
            sales_sqft = float(loc["SalesSqrFt"])
        except (TypeError, ValueError):
            sales_sqft = None

    annualized_spsf = None
    if sales_sqft and sales_sqft > 0 and ytd_days > 0:
        annualized_spsf = round(((ytd_sales / ytd_days) / sales_sqft) * 365, 2)

    lease = lease_status_for_store(sid)
    return {
        "storeId": sid,
        "asOf": as_of_iso,
        "location": loc,
        "salesSquareFt": sales_sqft,
        "ytdCoreSales": round(ytd_sales, 2),
        "ytdDays": ytd_days,
        "salesPerSqFtAnnualized": annualized_spsf,
        "leaseStatus": lease,
    }


def _sub_category_label_sql() -> str:
    """Retail subcategory bucket from TotalCoreTableFinal.[Sub_Category] (Books, Wares, Rack Sales, …)."""
    return (
        "COALESCE("
        "NULLIF(LTRIM(RTRIM(CAST(d.[Sub_Category] AS NVARCHAR(200)))), N''), "
        "N'(Unlabeled)')"
    )


def _sub_category_group_by_sql() -> str:
    return "LTRIM(RTRIM(CAST(d.[Sub_Category] AS NVARCHAR(200))))"


def _category_label_sql() -> str:
    """Legacy Category/RevenueType label (kept for non-subcategory rollups)."""
    cat = "NULLIF(LTRIM(RTRIM(CAST(d.[Category] AS NVARCHAR(200)))), N'')"
    rt = "NULLIF(LTRIM(RTRIM(CAST(d.[RevenueType] AS NVARCHAR(200)))), N'')"
    return (
        f"CASE "
        f"WHEN {cat} IS NOT NULL AND {rt} IS NOT NULL "
        f"     AND {cat} COLLATE Latin1_General_CI_AI <> {rt} COLLATE Latin1_General_CI_AI "
        f"  THEN {cat} + N' — ' + {rt} "
        f"ELSE COALESCE({rt}, {cat}, N'(Unlabeled)') "
        f"END"
    )


def _category_group_by_sql() -> str:
    return (
        "LTRIM(RTRIM(CAST(d.[Category] AS NVARCHAR(200)))), "
        "LTRIM(RTRIM(CAST(d.[RevenueType] AS NVARCHAR(200))))"
    )


def _is_single_core_sales_bucket(rows: list) -> bool:
    """True when TotalCore returns one Sub_Category line only."""
    labels = {
        str(r.get("RevenueCategory") or "").strip().lower()
        for r in (rows or [])
        if r
    }
    labels.discard("")
    labels.discard("(unlabeled)")
    return len(labels) <= 1


def _is_retail_core_category_label(label: str) -> bool:
    """Drop GL-style buckets that are not retail core-sales subcategories."""
    t = (label or "").strip().lower()
    if not t or t == "(unlabeled)":
        return False
    non_retail = (
        "liabilit",
        "asset",
        "payable",
        "receivable",
        "debt",
        "equity",
        "expense",
        "payroll",
        "depreciation",
        "amortization",
        "inventory adjustment",
        "cost of goods",
    )
    return not any(x in t for x in non_retail)


def _filter_retail_core_category_rows(rows: list) -> list:
    return [r for r in (rows or []) if _is_retail_core_category_label(str(r.get("RevenueCategory") or ""))]


def _gp_category_label_sql() -> str:
    return (
        "COALESCE("
        "NULLIF(LTRIM(RTRIM(CAST(d.SalesCategoryFromGP AS NVARCHAR(200)))), N''), "
        "N'(Unlabeled)')"
    )


def get_revenue_by_gp_category(store_id: str, start_date: str, end_date: str) -> list:
    """
    Revenue by GP sales category (SalesCategoryFromGP) from SalesFactFinal.
    Used for retail category mix when TotalCore only shows a single rollup bucket.
    """
    from db.static_locations import get_static_store_meta, sales_unit_name_for_store

    if _is_consolidated_location(store_id):
        return []

    obj = _validated_sales_line_object()
    cat_expr = _gp_category_label_sql()
    sum_rev = (
        "CAST(SUM(ISNULL(CAST(d.Revenue AS DECIMAL(18, 4)), 0)) AS DECIMAL(18, 2)) AS Revenue"
    )
    date_pred = (
        f"{SOLDTS_AS_DATE_SQL} >= CAST(? AS DATE) AND {SOLDTS_AS_DATE_SQL} <= CAST(? AS DATE)"
    )

    if Config.LOCATIONS_SOURCE == "static":
        meta = get_static_store_meta(store_id)
        if not meta:
            return []
        sold = meta.get("sold_store_id")
        unit = sales_unit_name_for_store(store_id)
        if sold is not None:
            sql = f"""
                SELECT {cat_expr} AS RevenueCategory, {sum_rev}
                FROM {obj} AS d
                WHERE TRY_CONVERT(DATETIME, d.Soldts) IS NOT NULL
                  AND d.SoldStoreId = ?
                  AND {date_pred}
                GROUP BY {cat_expr}
                HAVING SUM(ISNULL(CAST(d.Revenue AS DECIMAL(18, 4)), 0)) <> 0
                ORDER BY Revenue DESC
            """
            return _execute_query(sql, (int(sold), start_date, end_date))
        if not unit:
            return []
        unit_sql, unit_params = _sales_unit_name_predicate_sql(unit)
        sql = f"""
            SELECT {cat_expr} AS RevenueCategory, {sum_rev}
            FROM {obj} AS d
            WHERE TRY_CONVERT(DATETIME, d.Soldts) IS NOT NULL
            {unit_sql}
              AND {date_pred}
            GROUP BY {cat_expr}
            HAVING SUM(ISNULL(CAST(d.Revenue AS DECIMAL(18, 4)), 0)) <> 0
            ORDER BY Revenue DESC
        """
        return _execute_query(sql, (*unit_params, start_date, end_date))

    loc = resolve_location_reference(store_id)
    unit = sales_unit_name_for_store(str(loc["LocationID"])) if loc else None
    if not unit:
        unit = str(loc.get("LocationName") or "").strip() if loc else ""
    if not unit:
        return []
    unit_sql, unit_params = _sales_unit_name_predicate_sql(unit)
    sql = f"""
        SELECT {cat_expr} AS RevenueCategory, {sum_rev}
        FROM {obj} AS d
        WHERE TRY_CONVERT(DATETIME, d.Soldts) IS NOT NULL
        {unit_sql}
          AND {date_pred}
        GROUP BY {cat_expr}
        HAVING SUM(ISNULL(CAST(d.Revenue AS DECIMAL(18, 4)), 0)) <> 0
        ORDER BY Revenue DESC
    """
    return _execute_query(sql, (*unit_params, start_date, end_date))


def _category_rows_for_store(
    store_id: str,
    start_date: str,
    end_date: str,
    *,
    source: str = "total_core",
    core_sales_only: bool = True,
) -> Tuple[list, dict]:
    """
    Category/subcategory rows for chat — **TotalCoreTableFinal only** by default
    (same table as This Month core sales). Optional gp_line for explicit POS requests only.
    """
    if source == "gp_line":
        gp_rows = get_revenue_by_gp_category(store_id, start_date, end_date)
        return gp_rows, {
            "name": _validated_sales_line_object(),
            "grain": "gp_sales_category",
            "field": "SalesCategoryFromGP",
        }

    core_rows = _filter_retail_core_category_rows(
        get_revenue_by_category(store_id, start_date, end_date, core_sales_only=core_sales_only)
    )
    meta = {
        "name": _validated_this_month_revenue_object(),
        "grain": "total_core_subcategory",
        "field": "Sub_Category",
        "table": _validated_this_month_revenue_object(),
        "core_sales_filter": core_sales_only,
    }
    if _is_single_core_sales_bucket(core_rows):
        meta["single_bucket"] = True
        meta["note"] = (
            "TotalCoreTableFinal has only one retail category bucket for this store and month. "
            "Finer subcategories are not loaded in that table for this period."
        )
    return core_rows, meta


def get_revenue_by_category(
    store_id: str,
    start_date: str,
    end_date: str,
    *,
    core_sales_only: bool = True,
) -> list:
    """
    Subcategory breakdown from TotalCoreTableFinal.[Sub_Category] for any calendar month/range.
    When core_sales_only is True (default), applies the same Core Sales filter as This Month MTD.
    Returns rows: RevenueCategory (subcategory name), Revenue.
    """
    from db.static_locations import get_static_store_meta, sales_unit_name_for_store

    if _is_consolidated_location(store_id):
        return []

    meta = get_static_store_meta(store_id)
    if not meta and Config.LOCATIONS_SOURCE == "static":
        return []

    obj = _validated_this_month_revenue_object()
    cat_expr = _sub_category_label_sql()
    group_by = _sub_category_group_by_sql()
    sum_rev = (
        "CAST(SUM(ISNULL(CAST(d.[Revenue] AS DECIMAL(18, 4)), 0)) AS DECIMAL(18, 2)) AS Revenue"
    )
    core_sql, core_params = (
        _total_core_category_filter_sql() if core_sales_only else ("", ())
    )

    if Config.LOCATIONS_SOURCE == "static":
        sold = meta.get("sold_store_id") if meta else None
        ssu = meta.get("sales_store_unit") if meta else None
        uid = TOTAL_CORE_UNIT_LOCATION_ID_SQL
        unit = sales_unit_name_for_store(store_id)

        if unit:
            unit_sql, unit_params = _sales_unit_name_predicate_sql(unit)
            where = (
                f"WHERE 1 = 1 {unit_sql} {core_sql} "
                f"AND {TOTAL_CORE_DATE_SQL} >= CAST(? AS DATE) AND {TOTAL_CORE_DATE_SQL} <= CAST(? AS DATE)"
            )
            params = (*unit_params, *core_params, start_date, end_date)
        elif sold is not None:
            where = (
                f"WHERE {uid} = ? {core_sql} "
                f"AND {TOTAL_CORE_DATE_SQL} >= CAST(? AS DATE) AND {TOTAL_CORE_DATE_SQL} <= CAST(? AS DATE)"
            )
            params = (int(sold), *core_params, start_date, end_date)
        elif (store_id or "").strip().isdigit():
            where = (
                f"WHERE {uid} = ? {core_sql} "
                f"AND {TOTAL_CORE_DATE_SQL} >= CAST(? AS DATE) AND {TOTAL_CORE_DATE_SQL} <= CAST(? AS DATE)"
            )
            params = (int(store_id), *core_params, start_date, end_date)
        elif ssu is not None and str(ssu).strip():
            where = (
                "WHERE CHARINDEX(LTRIM(RTRIM(?)), LTRIM(RTRIM(CAST(d.[Unit] AS NVARCHAR(200))))) > 0 "
                f"{core_sql} "
                f"AND {TOTAL_CORE_DATE_SQL} >= CAST(? AS DATE) AND {TOTAL_CORE_DATE_SQL} <= CAST(? AS DATE)"
            )
            params = (str(ssu).strip(), *core_params, start_date, end_date)
        else:
            return []

        sql = f"""
            SELECT {cat_expr} AS RevenueCategory, {sum_rev}
            FROM {obj} AS d
            {where}
            GROUP BY {group_by}
            HAVING SUM(ISNULL(CAST(d.[Revenue] AS DECIMAL(18, 4)), 0)) <> 0
            ORDER BY Revenue DESC
        """
        return _execute_query(sql, params)

    loc_tbl = _validated_locations_table()
    sid = (store_id or "").strip()
    join_pred = _total_core_join_pred_database()
    sql = f"""
        SELECT {cat_expr} AS RevenueCategory, {sum_rev}
        FROM {obj} AS d
        INNER JOIN {loc_tbl} AS loc ON loc.LocationID = ?
        {join_pred}
        WHERE {TOTAL_CORE_DATE_SQL} >= CAST(? AS DATE)
          AND {TOTAL_CORE_DATE_SQL} <= CAST(? AS DATE)
          {core_sql}
        GROUP BY {group_by}
        HAVING SUM(ISNULL(CAST(d.[Revenue] AS DECIMAL(18, 4)), 0)) <> 0
        ORDER BY Revenue DESC
    """
    return _execute_query(sql, (sid, start_date, end_date, *core_params))


def compare_revenue_categories(
    store_ids: List[str],
    start_date: str,
    end_date: str,
) -> dict:
    """Category breakdown for up to three stores for chat/compare."""
    stores_out = []
    for sid in (store_ids or [])[:3]:
        ref = resolve_location_reference(str(sid).strip())
        if not ref:
            continue
        lid = str(ref.get("LocationID") or sid)
        rows, src = _category_rows_for_store(lid, start_date, end_date, core_sales_only=True)
        subtotal = sum(_coerce_number(r.get("Revenue")) for r in rows)
        fin_rows = get_financials(lid, start_date, end_date, this_month=True)
        core_total = round(_sum_field(fin_rows, "NetRevenue"), 2)
        stores_out.append(
            {
                "location_id": lid,
                "location_name": ref.get("LocationName"),
                "total_revenue": round(subtotal, 2),
                "core_sales_total_mtd": core_total,
                "category_source": src,
                "categories": [
                    {
                        "category": r.get("RevenueCategory"),
                        "revenue": round(_coerce_number(r.get("Revenue")), 2),
                    }
                    for r in rows
                ],
            }
        )
    primary_src = (
        stores_out[0].get("category_source")
        if stores_out
        else {"name": _validated_this_month_revenue_object(), "grain": "category_totals"}
    )
    return {
        "intent": "category_breakdown",
        "start": start_date,
        "end": end_date,
        "stores": stores_out,
        "source": primary_src,
        "data_table": _validated_this_month_revenue_object(),
        "data_grain": "total_core_subcategory",
    }


def get_donations(store_id: str, start_date: str, end_date: str) -> list:
    """
    Daily donation totals from tbl_Donation: SUM([DonationAmt]) per calendar day for one store.
    Storeid maps directly to the app/location id (e.g. 127). Consolidated sums every store.
    Returns rows: { DonationDate, Donations }.
    """
    obj = _validated_donations_object()
    dcol = _bracketed_col(Config.SQL_DONATIONS_COL_DATE, "SQL_DONATIONS_COL_DATE")
    scol = _bracketed_col(Config.SQL_DONATIONS_COL_STORE, "SQL_DONATIONS_COL_STORE")

    sum_amt = f"{_donations_sum_sql('d')} AS Donations"
    date_expr = f"CAST(d.{dcol} AS DATE)"

    if _is_consolidated_location(store_id):
        sql = f"""
            SELECT {date_expr} AS DonationDate, {sum_amt}
            FROM {obj} AS d
            WHERE {date_expr} BETWEEN ? AND ?
            GROUP BY {date_expr}
            ORDER BY {date_expr}
        """
        return _execute_query(sql, (start_date, end_date))

    sid = (store_id or "").strip()
    if not sid:
        return []
    # Storeid may be stored as nvarchar; compare as trimmed text to avoid int-conversion errors.
    store_match = f"LTRIM(RTRIM(CAST(d.{scol} AS NVARCHAR(50)))) = LTRIM(RTRIM(?))"
    sql = f"""
        SELECT {date_expr} AS DonationDate, {sum_amt}
        FROM {obj} AS d
        WHERE {store_match}
          AND {date_expr} BETWEEN ? AND ?
        GROUP BY {date_expr}
        ORDER BY {date_expr}
    """
    return _execute_query(sql, (sid, start_date, end_date))


def _donations_all_stores_daily(start_date: str, end_date: str) -> list:
    """ONE query: daily donation totals for every store (Storeid + date)."""
    obj = _validated_donations_object()
    dcol = _bracketed_col(Config.SQL_DONATIONS_COL_DATE, "SQL_DONATIONS_COL_DATE")
    scol = _bracketed_col(Config.SQL_DONATIONS_COL_STORE, "SQL_DONATIONS_COL_STORE")
    date_expr = f"CAST(d.{dcol} AS DATE)"
    sum_amt = f"{_donations_sum_sql('d')} AS Donations"
    sql = f"""
        SELECT
            LTRIM(RTRIM(CAST(d.{scol} AS NVARCHAR(50)))) AS StoreId,
            {date_expr} AS DonationDate,
            {sum_amt}
        FROM {obj} AS d
        WHERE {date_expr} BETWEEN ? AND ?
        GROUP BY LTRIM(RTRIM(CAST(d.{scol} AS NVARCHAR(50)))), {date_expr}
    """
    return _execute_query(sql, (start_date, end_date))


def _network_donations_by_store_day(scope: str, start_date: str, end_date: str) -> Dict[str, Dict[str, float]]:
    """{store id -> {date -> donation dollars}} across scoped locations."""
    idx = _scoped_location_index(scope)
    out: Dict[str, Dict[str, float]] = {}
    for r in _donations_all_stores_daily(start_date, end_date):
        sid = str(r.get("StoreId") or "").strip()
        if sid not in idx:
            continue
        dk = str(r.get("DonationDate"))[:10]
        out.setdefault(sid, {})
        out[sid][dk] = out[sid].get(dk, 0.0) + _coerce_number(r.get("Donations"))
    return out


def _budget_totals_by_location_static(start_date: str, end_date: str) -> list:
    """ONE query: actual/budget/variance totals per Unit location id for a date range."""
    obj = _validated_budget_vs_actual_object()
    cat_sql, cat_params = _budget_category_filter_sql()
    uid = TOTAL_CORE_UNIT_LOCATION_ID_SQL
    date_filter = (
        f"{BUDGET_DATE_SQL} >= CAST(? AS DATE) AND {BUDGET_DATE_SQL} <= CAST(? AS DATE)"
    )
    sql = f"""
        SELECT x.UnitLoc,
               CAST(SUM(x.Actual) AS DECIMAL(18, 2)) AS ActualRevenue,
               CAST(SUM(x.Budget) AS DECIMAL(18, 2)) AS BudgetRevenue,
               CAST(SUM(x.Variance) AS DECIMAL(18, 2)) AS RevenueVariance
        FROM (
            SELECT
                {uid} AS UnitLoc,
                ISNULL(CAST(d.[ActualCoreRevenue] AS DECIMAL(18, 4)), 0) AS Actual,
                ISNULL(CAST(d.[BudgetCoreRevenue] AS DECIMAL(18, 4)), 0) AS Budget,
                ISNULL(CAST(d.[RevenueVariance] AS DECIMAL(18, 4)), 0) AS Variance
            FROM {obj} AS d
            WHERE {date_filter}
            {cat_sql}
        ) AS x
        WHERE x.UnitLoc IS NOT NULL
        GROUP BY x.UnitLoc
    """
    return _execute_query(sql, (start_date, end_date, *cat_params))


def _budget_store_totals(scope: str, start_date: str, end_date: str) -> Dict[str, dict]:
    """{store id -> {actual, budget, variance, attainment_pct}} for scoped stores."""
    idx = _scoped_location_index(scope)
    out: Dict[str, dict] = {}
    if Config.LOCATIONS_SOURCE == "static":
        for r in _budget_totals_by_location_static(start_date, end_date):
            uid = r.get("UnitLoc")
            if uid is None:
                continue
            try:
                sid = str(int(uid))
            except (TypeError, ValueError):
                sid = str(uid).strip()
            if sid not in idx:
                continue
            actual = _coerce_number(r.get("ActualRevenue"))
            budget = _coerce_number(r.get("BudgetRevenue"))
            variance = _coerce_number(r.get("RevenueVariance"))
            attainment = round(100.0 * actual / budget, 1) if budget > 1e-9 else None
            out[sid] = {
                "actual": round(actual, 2),
                "budget": round(budget, 2),
                "variance": round(variance, 2),
                "attainment_pct": attainment,
            }
        return out

    def _work(loc):
        sid = str(loc["LocationID"]).strip()
        rows = get_budget_vs_actual(sid, start_date, end_date, grain="day")
        actual = _sum_field(rows, "ActualRevenue")
        budget = _sum_field(rows, "BudgetRevenue")
        variance = _sum_field(rows, "RevenueVariance")
        attainment = round(100.0 * actual / budget, 1) if budget > 1e-9 else None
        return sid, {
            "actual": round(actual, 2),
            "budget": round(budget, 2),
            "variance": round(variance, 2),
            "attainment_pct": attainment,
        }

    for sid, totals in _parallel_map(_work, list(idx.values())):
        out[sid] = totals
    return out


def budget_vs_actual_summary_for_store(
    store_id: str,
    start_date: str,
    end_date: str,
    *,
    timeframe_label: Optional[str] = None,
) -> dict:
    """Single-store actual vs budget totals for chat."""
    loc = resolve_location_reference(store_id)
    rows = get_budget_vs_actual(store_id, start_date, end_date, grain="day")
    actual = _sum_field(rows, "ActualRevenue")
    budget = _sum_field(rows, "BudgetRevenue")
    variance = _sum_field(rows, "RevenueVariance")
    attainment = round(100.0 * actual / budget, 1) if budget > 1e-9 else None
    tf = {"start": start_date, "end": end_date}
    if timeframe_label:
        tf["label"] = timeframe_label
    return {
        "intent": "budget_vs_actual",
        "metric": "budget_attainment",
        "scope": "location",
        "location_id": str(store_id),
        "location_name": loc.get("LocationName") if loc else None,
        "timeframe": tf,
        "actual_revenue": round(actual, 2),
        "budget_revenue": round(budget, 2),
        "revenue_variance": round(variance, 2),
        "attainment_pct": attainment,
        "over_budget": variance > 0 if variance is not None else None,
        "source": {"name": _validated_budget_vs_actual_object(), "grain": "daily_core_budget"},
    }


def rank_stores_budget_variance(
    start_date: str,
    end_date: str,
    *,
    scope: str = "all_retail_stores",
    limit: int = 10,
    timeframe_label: Optional[str] = None,
    sort: str = "attainment_desc",
) -> dict:
    """Rank stores by budget attainment or variance for chat."""
    _, scope_key = _retail_scope_filter(scope)
    idx = _scoped_location_index(scope)
    totals = _budget_store_totals(scope, start_date, end_date)
    rows = []
    for sid, loc in idx.items():
        t = totals.get(sid) or {}
        rows.append({
            "location_id": sid,
            "location_name": loc.get("LocationName"),
            "actual_revenue": t.get("actual", 0.0),
            "budget_revenue": t.get("budget", 0.0),
            "revenue_variance": t.get("variance", 0.0),
            "attainment_pct": t.get("attainment_pct"),
            "metric_value": t.get("attainment_pct") if t.get("attainment_pct") is not None else t.get("variance", 0.0),
        })
    reverse = sort != "attainment_asc"
    if sort in ("variance_desc", "variance_asc"):
        key_fn = lambda x: x.get("revenue_variance") or 0.0
        reverse = sort == "variance_desc"
    else:
        key_fn = lambda x: x.get("attainment_pct") if x.get("attainment_pct") is not None else -1e9
    ranked = sorted(rows, key=key_fn, reverse=reverse)[: max(1, min(int(limit), 25))]
    tf = {"start": start_date, "end": end_date}
    if timeframe_label:
        tf["label"] = timeframe_label
    return {
        "intent": "budget_vs_actual",
        "metric": "budget_attainment",
        "grain": "location",
        "scope": scope_key,
        "timeframe": tf,
        "locations": ranked,
        "source": {"name": _validated_budget_vs_actual_object(), "grain": "store_totals_for_range"},
    }


def rank_donation_days(
    start_date: str,
    end_date: str,
    *,
    scope: str = "all_retail_stores",
    limit: int = 5,
    timeframe_label: Optional[str] = None,
) -> dict:
    """Rank calendar days by network-wide donation totals."""
    _, scope_key = _retail_scope_filter(scope)
    by_store_day = _network_donations_by_store_day(scope_key, start_date, end_date)
    by_day: Dict[str, float] = {}
    for days in by_store_day.values():
        for d, v in days.items():
            by_day[d] = by_day.get(d, 0.0) + v
    cap = max(1, min(int(limit), 31))
    periods = sorted(
        [{"date": d, "metric_value": round(v, 2)} for d, v in by_day.items()],
        key=lambda x: x["metric_value"],
        reverse=True,
    )[:cap]
    tf = {"start": start_date, "end": end_date}
    if timeframe_label:
        tf["label"] = timeframe_label
    return {
        "metric": "donations",
        "grain": "day",
        "scope": scope_key,
        "timeframe": tf,
        "periods": periods,
        "source": {"name": _validated_donations_object(), "grain": "daily", "metric": "DonationAmt"},
    }


def rank_donation_days_for_store(
    store_id: str,
    start_date: str,
    end_date: str,
    *,
    limit: int = 5,
    timeframe_label: Optional[str] = None,
) -> dict:
    """Rank days by donation amount for one store."""
    rows = get_donations(store_id, start_date, end_date)
    day_rows: List[dict] = []
    for row in rows:
        dd = row.get("DonationDate")
        if dd is None:
            continue
        dk = dd.isoformat() if hasattr(dd, "isoformat") else str(dd)[:10]
        day_rows.append({"date": dk, "metric_value": round(_coerce_number(row.get("Donations")), 2)})
    day_rows.sort(key=lambda x: x["metric_value"], reverse=True)
    cap = max(1, min(int(limit), 31))
    loc = resolve_location_reference(store_id)
    tf = {"start": start_date, "end": end_date}
    if timeframe_label:
        tf["label"] = timeframe_label
    return {
        "metric": "donations",
        "grain": "day",
        "scope": "location",
        "location_id": str(store_id),
        "location_name": loc.get("LocationName") if loc else None,
        "timeframe": tf,
        "periods": day_rows[:cap],
        "source": {"name": _validated_donations_object(), "grain": "daily_single_store"},
    }


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


def _trends_month_filters(
    months: int = 12,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> tuple[str, str, tuple]:
    """Month window for trend rollups; uses explicit range when provided."""
    if start_date and end_date:
        month_window_start = (
            "DATEFROMPARTS(d.[Year], d.[Month], 1) >= "
            "DATEFROMPARTS(YEAR(CAST(? AS DATE)), MONTH(CAST(? AS DATE)), 1)"
        )
        month_window_end = (
            "DATEFROMPARTS(d.[Year], d.[Month], 1) <= "
            "DATEFROMPARTS(YEAR(CAST(? AS DATE)), MONTH(CAST(? AS DATE)), 1)"
        )
        return month_window_start, month_window_end, (start_date, end_date)
    month_window_start = (
        "DATEFROMPARTS(d.[Year], d.[Month], 1) >= "
        "DATEADD(MONTH, 1 - ?, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))"
    )
    month_window_end = (
        "DATEFROMPARTS(d.[Year], d.[Month], 1) <= "
        "DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)"
    )
    return month_window_start, month_window_end, (max(1, int(months)),)


def _donations_monthly_join_sql(
    store_id: str,
    daily_start: str,
    daily_end: str,
) -> tuple:
    """Monthly donation totals for trends, scoped to the same daily window as the chart."""
    obj = _validated_donations_object()
    dcol = _bracketed_col(Config.SQL_DONATIONS_COL_DATE, "SQL_DONATIONS_COL_DATE")
    scol = _bracketed_col(Config.SQL_DONATIONS_COL_STORE, "SQL_DONATIONS_COL_STORE")
    date_expr = f"CAST(d.{dcol} AS DATE)"
    sum_amt = _donations_sum_sql("d")
    date_filter = f" AND {date_expr} >= CAST(? AS DATE) AND {date_expr} <= CAST(? AS DATE) "

    if _is_consolidated_location(store_id):
        inner_where = f" WHERE 1 = 1 {date_filter} "
        params: tuple = (daily_start, daily_end)
    else:
        sid = (store_id or "").strip()
        store_match = f"LTRIM(RTRIM(CAST(d.{scol} AS NVARCHAR(50)))) = LTRIM(RTRIM(?))"
        inner_where = f" WHERE {store_match} {date_filter} "
        params = (sid, daily_start, daily_end)

    join = f"""
        LEFT JOIN (
            SELECT
                DATEFROMPARTS(YEAR({date_expr}), MONTH({date_expr}), 1) AS MonthStart,
                {sum_amt} AS TotalDonations
            FROM {obj} AS d
            {inner_where}
            GROUP BY YEAR({date_expr}), MONTH({date_expr})
        ) dn ON agg.PeriodMonth = dn.MonthStart
    """
    return join, params


def get_trends(
    store_id: str,
    months: int = 12,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list:
    """Trend tab: monthly financials + door counts + donations (all aligned to the same window)."""
    daily_start, daily_end = _resolve_trend_daily_window(months, start_date, end_date)

    ids = _resolve_pcounter_location_ids(store_id)
    tbl = _validated_door_count_object()
    dcol = _bracketed_col(Config.SQL_DOOR_COUNT_COL_DATE, "SQL_DOOR_COUNT_COL_DATE")
    vcol = _bracketed_col(Config.SQL_DOOR_COUNT_COL_VISITS, "SQL_DOOR_COUNT_COL_VISITS")
    lcol = _bracketed_col(Config.SQL_DOOR_COUNT_COL_LOCATION, "SQL_DOOR_COUNT_COL_LOCATION")
    obj = _validated_retail_monthly_financial_object()
    door_date_filter = (
        f" AND CAST({dcol} AS DATE) >= CAST(? AS DATE) AND CAST({dcol} AS DATE) <= CAST(? AS DATE) "
    )
    door_date_params = (daily_start, daily_end)

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
                {door_date_filter}
                GROUP BY CAST({dcol} AS DATE)
            ) d
            GROUP BY DATEFROMPARTS(YEAR(CountDate), MONTH(CountDate), 1)
        ) dc ON agg.PeriodMonth = dc.MonthStart
        """
        door_params = tuple(ids) + door_date_params
    else:
        door_join = """
        LEFT JOIN (
            SELECT CAST(NULL AS DATE) AS MonthStart, CAST(0 AS INT) AS TotalVisits WHERE 1 = 0
        ) dc ON agg.PeriodMonth = dc.MonthStart
        """
        door_params = ()

    donations_join, donations_params = _donations_monthly_join_sql(
        store_id, daily_start, daily_end
    )

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

    month_window_start, month_window_end, window_params = _trends_month_filters(
        months, start_date, end_date
    )

    if _is_consolidated_location(store_id):
        sql = f"""
            SELECT
                agg.PeriodMonth,
                agg.NetRevenue,
                agg.NetIncome,
                agg.ExpenseRatio,
                CAST(0 AS DECIMAL(18, 2)) AS DonatedGoodsRev,
                CAST(0 AS DECIMAL(18, 2)) AS RetailRevenue,
                ISNULL(dc.TotalVisits, 0) AS DoorCount,
                ISNULL(dn.TotalDonations, 0) AS Donations
            FROM (
                SELECT
                    {agg_select}
                FROM {obj} AS d
                WHERE {month_window_start}
                  AND {month_window_end}
                GROUP BY d.[Year], d.[Month]
            ) AS agg
            {door_join}
            {donations_join}
            ORDER BY agg.PeriodMonth
        """
        return _execute_query(sql, window_params + door_params + donations_params)

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
                ISNULL(dc.TotalVisits, 0) AS DoorCount,
                ISNULL(dn.TotalDonations, 0) AS Donations
            FROM (
                SELECT
                    {agg_select}
                FROM {obj} AS d
                WHERE {month_window_start}
                  AND {month_window_end}
                {unit_sql}
                GROUP BY d.[Year], d.[Month]
            ) AS agg
            {door_join}
            {donations_join}
            ORDER BY agg.PeriodMonth
        """
        return _execute_query(sql, window_params + unit_params + door_params + donations_params)

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
            ISNULL(dc.TotalVisits, 0) AS DoorCount,
            ISNULL(dn.TotalDonations, 0) AS Donations
        FROM (
            SELECT
                {agg_select}
            FROM {obj} AS d
            INNER JOIN {loc_tbl} AS loc
              ON loc.LocationID = ?
            {join_name}
            WHERE {month_window_start}
              AND {month_window_end}
            GROUP BY d.[Year], d.[Month]
        ) AS agg
        {door_join}
        {donations_join}
        ORDER BY agg.PeriodMonth
    """
    return _execute_query(sql, (sid,) + window_params + door_params + donations_params)


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


def _is_current_month_timeframe(start: str, end: str, current_day: date) -> bool:
    """TotalCoreTableFinal is the daily current-month source; older periods use monthly financials."""
    try:
        start_day = date.fromisoformat(start)
        end_day = date.fromisoformat(end)
    except (TypeError, ValueError):
        return False
    return (
        start_day.year == current_day.year
        and start_day.month == current_day.month
        and end_day.year == current_day.year
        and end_day.month == current_day.month
    )


def compare_locations(metric: str, store_refs: list, today: Optional[date] = None, timeframe: Optional[dict] = None) -> dict:
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
    if timeframe:
        start = timeframe["start"]
        end = timeframe["end"]
    else:
        start = ""
        end = ""

    if metric == "door_count":
        if not timeframe:
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
    elif metric == "donations":
        if not timeframe:
            start = _month_start(current_day).isoformat()
            end = current_day.isoformat()
        for loc in resolved:
            lid = str(loc["LocationID"])
            rows = get_donations(lid, start, end)
            comparisons.append({
                "location_id": lid,
                "location_name": loc.get("LocationName"),
                "metric_value": round(_sum_field(rows, "Donations"), 2),
            })
        timeframe = {"start": start, "end": end}
    else:
        if not timeframe:
            start = _month_start(current_day).isoformat()
            end = current_day.isoformat()
        mkey = metric if metric in {
            "revenue", "donations", "net_income", "operating_expenses", "personnel_expenses", "expense_ratio",
        } else "revenue"
        for loc in resolved:
            lid = str(loc["LocationID"])
            val = _location_metric_total(lid, mkey, start, end, current_day)
            if mkey == "expense_ratio":
                mv = round(val, 4)
            elif mkey == "door_count":
                mv = int(round(val))
            elif mkey == "donations":
                mv = round(val, 2)
            else:
                mv = round(val, 2)
            comparisons.append({
                "location_id": lid,
                "location_name": loc.get("LocationName"),
                "metric_value": mv,
            })
        timeframe = {"start": start, "end": end}

    ordered = sorted(comparisons, key=lambda item: item["metric_value"], reverse=True)
    return {
        "metric": metric,
        "timeframe": timeframe,
        "locations": comparisons,
        "leader": ordered[0] if ordered else None,
    }


def rank_locations(metric: str, limit: int = 5, today: Optional[date] = None, timeframe: Optional[dict] = None) -> dict:
    """Rank locations by an approved metric using parameterized queries only."""
    current_day = today or date.today()
    idx = _scoped_location_index("all_locations")
    rows = []
    if timeframe:
        start = timeframe["start"]
        end = timeframe["end"]
    else:
        start = ""
        end = ""

    if metric == "door_count":
        if not timeframe:
            start = (current_day - timedelta(days=29)).isoformat()
            end = current_day.isoformat()
        door_map = _network_door_by_store_day("all_locations", start, end)
        for sid, loc in idx.items():
            rows.append({
                "location_id": sid,
                "location_name": loc.get("LocationName"),
                "metric_value": int(round(sum(door_map.get(sid, {}).values()))),
            })
    elif metric == "donations":
        if not timeframe:
            start = _month_start(current_day).isoformat()
            end = current_day.isoformat()
        don_map = _network_donations_by_store_day("all_locations", start, end)
        for sid, loc in idx.items():
            rows.append({
                "location_id": sid,
                "location_name": loc.get("LocationName"),
                "metric_value": round(sum(don_map.get(sid, {}).values()), 2),
            })
    else:
        if not timeframe:
            start = _month_start(current_day).isoformat()
            end = current_day.isoformat()
        mkey = metric if metric in {
            "revenue", "net_income", "operating_expenses", "personnel_expenses", "expense_ratio",
        } else "revenue"
        if mkey == "revenue":
            rev_map = _network_revenue_by_store_day("all_locations", start, end)
            for sid, loc in idx.items():
                rows.append({
                    "location_id": sid,
                    "location_name": loc.get("LocationName"),
                    "metric_value": round(sum(rev_map.get(sid, {}).values()), 2),
                })
        else:
            for lid, name, val in _parallel_store_metric_totals(
                list(idx.values()), mkey, start, end, current_day
            ):
                mv = round(val, 4) if mkey == "expense_ratio" else round(val, 2)
                rows.append({
                    "location_id": lid,
                    "location_name": name,
                    "metric_value": mv,
                })

    ranked = sorted(rows, key=lambda item: item["metric_value"], reverse=True)[:max(1, min(limit, 10))]
    return {
        "metric": metric,
        "timeframe": timeframe or {"start": start, "end": end},
        "locations": ranked,
    }


def _sql_parallel_workers(job_count: int) -> int:
    """Bounded worker count for parallel per-store queries (capped to the connection pool size)."""
    jc = max(0, int(job_count))
    if jc <= 0:
        return 1
    pool_cap = int(getattr(Config, "SQL_POOL_MAX_SIZE", 12) or 12)
    return max(1, min(16, pool_cap, jc))


def _parallel_map(fn, items: list) -> list:
    """Run ``fn`` over items concurrently (bounded). Returns results in completion order."""
    items = list(items)
    if not items:
        return []
    if len(items) == 1:
        return [fn(items[0])]
    workers = _sql_parallel_workers(len(items))
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(fn, it) for it in items]
        for fu in concurrent.futures.as_completed(futs):
            results.append(fu.result())
    return results


def _scoped_location_index(scope: str) -> Dict[str, dict]:
    """{app store id -> location dict} for non-consolidated locations in scope."""
    return {str(loc["LocationID"]).strip(): loc for loc in _iterate_scoped_locations(scope)}


def _core_revenue_by_location_day_static(start_date: str, end_date: str) -> list:
    """
    ONE query: daily Core revenue for EVERY store, grouped by the Unit location id and date.

    Replaces the old fan-out where each store ran its own full scan of TotalCoreTableFinal.
    The Unit location id (3rd hyphen segment) maps directly to the app/location id in static mode.
    """
    obj = _validated_this_month_revenue_object()
    cat_sql, cat_params = _total_core_category_filter_sql()
    uid = TOTAL_CORE_UNIT_LOCATION_ID_SQL
    sql = f"""
        SELECT x.UnitLoc, x.SalesDate,
               CAST(SUM(x.Rev) AS DECIMAL(18, 2)) AS NetRevenue
        FROM (
            SELECT
                {uid} AS UnitLoc,
                {TOTAL_CORE_DATE_SQL} AS SalesDate,
                ISNULL(CAST(d.[Revenue] AS DECIMAL(18, 4)), 0) AS Rev
            FROM {obj} AS d
            WHERE {TOTAL_CORE_DATE_SQL} >= CAST(? AS DATE)
              AND {TOTAL_CORE_DATE_SQL} <= CAST(? AS DATE)
              {cat_sql}
        ) AS x
        WHERE x.UnitLoc IS NOT NULL
        GROUP BY x.UnitLoc, x.SalesDate
        ORDER BY x.SalesDate
    """
    return _execute_query(sql, (start_date, end_date, *cat_params))


def _door_visits_by_location_day(location_ids: list, start_date: str, end_date: str) -> list:
    """ONE query: daily donor visits per PeopleCounter LocationID across the given ids."""
    if not location_ids:
        return []
    tbl = _validated_door_count_object()
    dcol = _bracketed_col(Config.SQL_DOOR_COUNT_COL_DATE, "SQL_DOOR_COUNT_COL_DATE")
    vcol = _bracketed_col(Config.SQL_DOOR_COUNT_COL_VISITS, "SQL_DOOR_COUNT_COL_VISITS")
    lcol = _bracketed_col(Config.SQL_DOOR_COUNT_COL_LOCATION, "SQL_DOOR_COUNT_COL_LOCATION")
    ph = ",".join("?" * len(location_ids))
    sql = f"""
        SELECT {lcol} AS LocationID, CAST({dcol} AS DATE) AS CountDate, SUM({vcol}) AS DonorVisits
        FROM {tbl}
        WHERE {lcol} IN ({ph})
          AND CAST({dcol} AS DATE) BETWEEN ? AND ?
        GROUP BY {lcol}, CAST({dcol} AS DATE)
    """
    return _execute_query(sql, tuple(location_ids) + (start_date, end_date))


def _network_revenue_by_store_day(scope: str, start_date: str, end_date: str) -> Dict[str, Dict[str, float]]:
    """{store id -> {date -> core revenue}} across scope. Static: 1 query; DB mode: parallel per-store."""
    idx = _scoped_location_index(scope)
    out: Dict[str, Dict[str, float]] = {}

    if Config.LOCATIONS_SOURCE == "static":
        for r in _core_revenue_by_location_day_static(start_date, end_date):
            uid = r.get("UnitLoc")
            if uid is None:
                continue
            try:
                sid = str(int(uid))
            except (TypeError, ValueError):
                sid = str(uid).strip()
            if sid not in idx:
                continue
            dk = str(r.get("SalesDate"))[:10]
            out.setdefault(sid, {})
            out[sid][dk] = out[sid].get(dk, 0.0) + _coerce_number(r.get("NetRevenue"))
        return out

    def _work(loc):
        sid = str(loc["LocationID"]).strip()
        frag: Dict[str, float] = {}
        for row in get_financials(sid, start_date, end_date, this_month=True):
            sd = row.get("SalesDate")
            if sd is None:
                continue
            dk = sd.isoformat()[:10] if hasattr(sd, "isoformat") else str(sd)[:10]
            frag[dk] = frag.get(dk, 0.0) + _coerce_number(row.get("NetRevenue"))
        return sid, frag

    for sid, frag in _parallel_map(_work, list(idx.values())):
        if frag:
            out[sid] = frag
    return out


def _network_door_by_store_day(scope: str, start_date: str, end_date: str) -> Dict[str, Dict[str, float]]:
    """{store id -> {date -> donor visits}} across scope, resolved in ONE PeopleCounter query."""
    idx = _scoped_location_index(scope)
    pid_to_store: Dict[int, str] = {}
    for sid in idx:
        for pid in _resolve_pcounter_location_ids(sid):
            try:
                pid_to_store[int(pid)] = sid
            except (TypeError, ValueError):
                continue

    out: Dict[str, Dict[str, float]] = {}
    if not pid_to_store:
        return out
    for r in _door_visits_by_location_day(sorted(pid_to_store.keys()), start_date, end_date):
        pid = r.get("LocationID")
        try:
            sid = pid_to_store.get(int(pid))
        except (TypeError, ValueError):
            sid = None
        if not sid:
            continue
        dk = str(r.get("CountDate"))[:10]
        out.setdefault(sid, {})
        out[sid][dk] = out[sid].get(dk, 0.0) + _coerce_number(r.get("DonorVisits"))
    return out


def _parallel_store_metric_totals(
    locs: list, metric: str, start_date: str, end_date: str, current_day: date
) -> list:
    """Concurrent per-store totals for metrics sourced from the monthly financial table.

    Returns list of (location_id, location_name, value). Used for net_income / expenses /
    expense_ratio where there is no single set-based grouping key (name-matched monthly table).
    """
    def _work(loc):
        lid = str(loc["LocationID"])
        return lid, loc.get("LocationName"), _location_metric_total(lid, metric, start_date, end_date, current_day)

    return _parallel_map(_work, list(locs))


def _peak_daily_candidates_for_location(loc: dict, start_date: str, end_date: str) -> List[dict]:
    lid = str(loc["LocationID"])
    rows = get_financials(lid, start_date, end_date, this_month=True)
    out = []
    for row in rows:
        sd = row.get("SalesDate")
        if sd is None:
            continue
        dk = sd.isoformat() if hasattr(sd, "isoformat") else str(sd)[:10]
        rev = _coerce_number(row.get("NetRevenue"))
        out.append({
            "location_id": lid,
            "location_name": loc.get("LocationName"),
            "date": dk,
            "metric_value": round(rev, 2),
        })
    return out


def _revenue_days_fragment(loc: dict, start_date: str, end_date: str, allowed_types: Optional[frozenset]) -> Dict[str, float]:
    lid = str(loc.get("LocationID", "") or "").strip()
    if _is_consolidated_location(lid):
        return {}
    lt = str(loc.get("LocationType") or "").strip().lower()
    if allowed_types is not None and lt not in allowed_types:
        return {}
    fragment: Dict[str, float] = {}
    rows = get_financials(lid, start_date, end_date, this_month=True)
    for row in rows:
        sd = row.get("SalesDate")
        if sd is None:
            continue
        dk = sd.isoformat() if hasattr(sd, "isoformat") else str(sd)[:10]
        val = row.get("NetRevenue")
        fv = float(_coerce_number(val)) if val is not None else 0.0
        fragment[dk] = fragment.get(dk, 0.0) + fv
    return fragment


def _door_count_days_fragment(loc: dict, start_date: str, end_date: str, allowed_types: Optional[frozenset]) -> Dict[str, float]:
    lid = str(loc.get("LocationID", "") or "").strip()
    if _is_consolidated_location(lid):
        return {}
    lt = str(loc.get("LocationType") or "").strip().lower()
    if allowed_types is not None and lt not in allowed_types:
        return {}
    fragment: Dict[str, float] = {}
    rows = get_door_count(lid, start_date, end_date)
    for row in rows:
        cd = row.get("CountDate")
        if cd is None:
            continue
        dk = cd.isoformat() if hasattr(cd, "isoformat") else str(cd)[:10]
        fragment[dk] = fragment.get(dk, 0.0) + float(_coerce_number(row.get("DonorVisits")))
    return fragment


def _merge_numeric_day_maps(target: Dict[str, float], fragment: Dict[str, float]) -> None:
    for k, v in fragment.items():
        target[k] = target.get(k, 0.0) + v


def _retail_scope_filter(scope: str) -> Tuple[Optional[frozenset], str]:
    """Return (allowed lowercased LocationType set, scope label) or (None for all non-consolidated)."""
    sl = (scope or "all_retail_stores").strip().lower()
    if sl in {"all_retail_stores", "retail"}:
        return frozenset({"store", "outlet"}), "all_retail_stores"
    if sl in {"all_locations", "locations"}:
        return None, "all_locations"
    return frozenset({"store", "outlet"}), "all_retail_stores"


def rank_revenue_days(
    start_date: str,
    end_date: str,
    *,
    scope: str = "all_retail_stores",
    limit: int = 5,
    timeframe_label: Optional[str] = None,
) -> dict:
    """
    Sum daily revenue across locations from TotalCoreTableFinal via per-store approved daily queries.
    Used for \"which day had the highest sales\" across retail stores.
    """
    _, scope_key = _retail_scope_filter(scope)
    by_store_day = _network_revenue_by_store_day(scope_key, start_date, end_date)
    by_day: Dict[str, float] = {}
    for days in by_store_day.values():
        for d, v in days.items():
            by_day[d] = by_day.get(d, 0.0) + v

    cap = max(1, min(int(limit), 31))
    periods = sorted(
        [{"date": d, "metric_value": round(v, 2)} for d, v in by_day.items()],
        key=lambda x: x["metric_value"],
        reverse=True,
    )[:cap]

    obj_name = _validated_this_month_revenue_object()
    cat = (Config.SQL_SALES_CORE_CATEGORY or "").strip()
    filter_notes: List[str] = ["retail locations: store + outlet"] if scope_key == "all_retail_stores" else []
    if cat:
        filter_notes.append(f"Category/RevenueType = {cat}")

    tf = {"start": start_date, "end": end_date}
    if timeframe_label:
        tf["label"] = timeframe_label

    return {
        "metric": "revenue",
        "grain": "day",
        "scope": scope_key,
        "timeframe": tf,
        "periods": periods,
        "source": {
            "name": obj_name,
            "grain": "daily",
            "metric": "NetRevenue (Core)",
            "date_range": f"{start_date} to {end_date}",
            "filters": filter_notes,
        },
    }


def rank_revenue_days_for_store(
    store_id: str,
    start_date: str,
    end_date: str,
    *,
    limit: int = 5,
    timeframe_label: Optional[str] = None,
) -> dict:
    """
    Rank days by core revenue for one location using TotalCoreTableFinal daily rows
    (via get_financials with this_month=True).
    """
    rows = get_financials(store_id, start_date, end_date, this_month=True)
    day_rows: List[dict] = []
    for row in rows:
        sd = row.get("SalesDate")
        if sd is None:
            continue
        dk = sd.isoformat() if hasattr(sd, "isoformat") else str(sd)[:10]
        val = float(_coerce_number(row.get("NetRevenue")))
        day_rows.append({"date": dk, "metric_value": round(val, 2)})
    day_rows.sort(key=lambda x: x["metric_value"], reverse=True)
    cap = max(1, min(int(limit), 31))
    periods = day_rows[:cap]

    loc = resolve_location_reference(store_id)
    tf = {"start": start_date, "end": end_date}
    if timeframe_label:
        tf["label"] = timeframe_label
    obj_name = _validated_this_month_revenue_object()
    cat = (Config.SQL_SALES_CORE_CATEGORY or "").strip()
    filter_notes: List[str] = [f"single store: {loc.get('LocationName') if loc else store_id}"]
    if cat:
        filter_notes.append(f"Category/RevenueType = {cat}")

    return {
        "metric": "revenue",
        "grain": "day",
        "scope": "location",
        "location_id": str(store_id),
        "location_name": loc.get("LocationName") if loc else None,
        "timeframe": tf,
        "periods": periods,
        "source": {
            "name": obj_name,
            "grain": "daily",
            "metric": "NetRevenue (Core) single store",
            "date_range": f"{start_date} to {end_date}",
            "filters": filter_notes,
        },
    }


def rank_door_count_days_for_store(
    store_id: str,
    start_date: str,
    end_date: str,
    *,
    limit: int = 5,
    timeframe_label: Optional[str] = None,
) -> dict:
    """Rank days by donor visits for one store (PCounter daily rollup)."""
    rows = get_door_count(store_id, start_date, end_date)
    day_rows: List[dict] = []
    for row in rows:
        cd = row.get("CountDate")
        if cd is None:
            continue
        dk = cd.isoformat() if hasattr(cd, "isoformat") else str(cd)[:10]
        val = float(_coerce_number(row.get("DonorVisits")))
        day_rows.append({"date": dk, "metric_value": int(round(val))})
    day_rows.sort(key=lambda x: x["metric_value"], reverse=True)
    cap = max(1, min(int(limit), 31))
    periods = day_rows[:cap]

    loc = resolve_location_reference(store_id)
    tf = {"start": start_date, "end": end_date}
    if timeframe_label:
        tf["label"] = timeframe_label
    tbl = _validated_door_count_object()
    return {
        "metric": "door_count",
        "grain": "day",
        "scope": "location",
        "location_id": str(store_id),
        "location_name": loc.get("LocationName") if loc else None,
        "timeframe": tf,
        "periods": periods,
        "source": {
            "name": tbl,
            "grain": "daily",
            "metric": "DonorVisits single store",
            "date_range": f"{start_date} to {end_date}",
            "filters": [f"single store: {loc.get('LocationName') if loc else store_id}"],
        },
    }


def rank_door_count_days(
    start_date: str,
    end_date: str,
    *,
    scope: str = "all_retail_stores",
    limit: int = 5,
    timeframe_label: Optional[str] = None,
) -> dict:
    """Rank calendar days by total door count summed across scoped locations (single SQL when possible)."""
    allowed_types, scope_key = _retail_scope_filter(scope)
    tbl = _validated_door_count_object()
    by_day: Dict[str, float] = {}

    all_ids = _collect_pcounter_ids_for_scope(scope)
    if all_ids:
        dcol = _bracketed_col(Config.SQL_DOOR_COUNT_COL_DATE, "SQL_DOOR_COUNT_COL_DATE")
        vcol = _bracketed_col(Config.SQL_DOOR_COUNT_COL_VISITS, "SQL_DOOR_COUNT_COL_VISITS")
        lcol = _bracketed_col(Config.SQL_DOOR_COUNT_COL_LOCATION, "SQL_DOOR_COUNT_COL_LOCATION")
        ph = ",".join("?" * len(all_ids))
        sql = f"""
            SELECT CAST({dcol} AS DATE) AS CountDate, SUM({vcol}) AS DonorVisits
            FROM {tbl}
            WHERE {lcol} IN ({ph})
              AND CAST({dcol} AS DATE) BETWEEN ? AND ?
            GROUP BY CAST({dcol} AS DATE)
        """
        rows_agg = _execute_query(sql, tuple(all_ids) + (start_date, end_date))
        for row in rows_agg:
            cd = row.get("CountDate")
            if cd is None:
                continue
            dk = cd.isoformat() if hasattr(cd, "isoformat") else str(cd)[:10]
            by_day[dk] = float(_coerce_number(row.get("DonorVisits")))
    else:
        locations = get_locations()
        if len(locations) <= 1:
            for loc in locations:
                _merge_numeric_day_maps(by_day, _door_count_days_fragment(loc, start_date, end_date, allowed_types))
        else:
            workers = _sql_parallel_workers(len(locations))
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                futs = [
                    pool.submit(_door_count_days_fragment, loc, start_date, end_date, allowed_types)
                    for loc in locations
                ]
                for fu in concurrent.futures.as_completed(futs):
                    _merge_numeric_day_maps(by_day, fu.result())

    cap = max(1, min(int(limit), 31))
    periods = sorted(
        [{"date": d, "metric_value": int(round(v))} for d, v in by_day.items()],
        key=lambda x: x["metric_value"],
        reverse=True,
    )[:cap]

    tf = {"start": start_date, "end": end_date}
    if timeframe_label:
        tf["label"] = timeframe_label

    return {
        "metric": "door_count",
        "grain": "day",
        "scope": scope_key,
        "timeframe": tf,
        "periods": periods,
        "source": {
            "name": tbl,
            "grain": "daily",
            "metric": f"SUM({Config.SQL_DOOR_COUNT_COL_VISITS})",
            "date_range": f"{start_date} to {end_date}",
            "filters": (
                ["retail locations: store + outlet"] if scope_key == "all_retail_stores" else []
            ),
        },
    }


def _iterate_scoped_locations(scope: str) -> List[dict]:
    allowed_types, _ = _retail_scope_filter(scope)
    out = []
    for loc in get_locations():
        lid = str(loc.get("LocationID", "") or "").strip()
        if _is_consolidated_location(lid):
            continue
        lt = str(loc.get("LocationType") or "").strip().lower()
        if allowed_types is not None and lt not in allowed_types:
            continue
        out.append(loc)
    return out


def _collect_pcounter_ids_for_scope(scope: str) -> List[int]:
    """All PeopleCounter LocationIDs for retail locations in scope (for single set-based rollup)."""
    seen = set()
    for loc in _iterate_scoped_locations(scope):
        lid = str(loc.get("LocationID", "") or "").strip()
        for pid in _resolve_pcounter_location_ids(lid):
            try:
                seen.add(int(pid))
            except (TypeError, ValueError):
                continue
    return sorted(seen)


def _location_metric_total(
    location_id: str,
    metric: str,
    start: str,
    end: str,
    current_day: date,
) -> float:
    """Single-location aggregate for ranking / breakdowns."""
    if metric == "door_count":
        return float(int(round(_sum_field(get_door_count(location_id, start, end), "DonorVisits"))))
    if metric == "donations":
        return _sum_field(get_donations(location_id, start, end), "Donations")
    if metric in {"net_income", "operating_expenses", "personnel_expenses"}:
        rows = get_financials(location_id, start, end, this_month=False)
        field = {
            "net_income": "NetIncome",
            "operating_expenses": "OperatingExpenses",
            "personnel_expenses": "TotalPersonnelExpenses",
        }[metric]
        return _sum_field(rows, field)
    if metric == "expense_ratio":
        rows = get_financials(location_id, start, end, this_month=False)
        vals = [
            _coerce_number(r.get("ExpenseRatio"))
            for r in rows
            if r.get("ExpenseRatio") is not None
        ]
        return sum(vals) / len(vals) if vals else 0.0
    # Revenue: sum daily core rows from TotalCoreTableFinal for the requested start/end dates.
    # The get_financials flag is misnamed (`this_month`); False uses monthly financial summary only,
    # which hides true daily grain and misaligns totals outside the server's current calendar month.
    rows = get_financials(location_id, start, end, this_month=True)
    return _sum_field(rows, "NetRevenue")


def rank_store_revenue(
    start_date: str,
    end_date: str,
    *,
    metric: str = "revenue",
    scope: str = "all_retail_stores",
    limit: int = 10,
    timeframe_label: Optional[str] = None,
    today: Optional[date] = None,
) -> dict:
    """
    Rank stores/outlets in scope by an approved metric (spec: store breakdown for a day or month).
    """
    current_day = today or date.today()
    _, scope_key = _retail_scope_filter(scope)
    cap = max(1, min(int(limit), 25))
    rank_metric = metric if metric != "revenue" else "revenue"
    if rank_metric == "revenue":
        fn_metric = "revenue"
    elif rank_metric not in {
        "door_count", "donations", "net_income", "operating_expenses", "personnel_expenses", "expense_ratio",
    }:
        fn_metric = "revenue"
    else:
        fn_metric = rank_metric

    idx = _scoped_location_index(scope)
    rows = []
    if fn_metric == "revenue":
        rev_map = _network_revenue_by_store_day(scope, start_date, end_date)
        for sid, loc in idx.items():
            rows.append({
                "location_id": sid,
                "location_name": loc.get("LocationName"),
                "metric_value": round(sum(rev_map.get(sid, {}).values()), 2),
            })
    elif fn_metric == "door_count":
        door_map = _network_door_by_store_day(scope, start_date, end_date)
        for sid, loc in idx.items():
            rows.append({
                "location_id": sid,
                "location_name": loc.get("LocationName"),
                "metric_value": int(round(sum(door_map.get(sid, {}).values()))),
            })
    elif fn_metric == "donations":
        don_map = _network_donations_by_store_day(scope, start_date, end_date)
        for sid, loc in idx.items():
            rows.append({
                "location_id": sid,
                "location_name": loc.get("LocationName"),
                "metric_value": round(sum(don_map.get(sid, {}).values()), 2),
            })
    else:
        for lid, name, val in _parallel_store_metric_totals(
            list(idx.values()), fn_metric, start_date, end_date, current_day
        ):
            mv = round(val, 4) if fn_metric == "expense_ratio" else round(val, 2)
            rows.append({
                "location_id": lid,
                "location_name": name,
                "metric_value": mv,
            })

    ranked = sorted(rows, key=lambda item: item["metric_value"], reverse=True)[:cap]
    tf = {"start": start_date, "end": end_date}
    if timeframe_label:
        tf["label"] = timeframe_label

    rev_obj = _validated_this_month_revenue_object()
    month_obj = _validated_retail_monthly_financial_object()
    if fn_metric == "revenue":
        primary_src = rev_obj
    elif fn_metric == "door_count":
        primary_src = _validated_door_count_object()
    else:
        primary_src = month_obj
    src = {
        "name": primary_src,
        "grain": "location_total_for_range",
        "metric": fn_metric,
        "date_range": f"{start_date} to {end_date}",
        "filters": (
            ["retail locations: store + outlet"] if scope_key == "all_retail_stores" else []
        ),
    }

    return {
        "metric": fn_metric,
        "grain": "location",
        "scope": scope_key,
        "timeframe": tf,
        "locations": ranked,
        "source": src,
    }


def peak_store_daily_revenue(
    start_date: str,
    end_date: str,
    *,
    scope: str = "all_retail_stores",
    timeframe_label: Optional[str] = None,
    top_pairs: int = 5,
) -> dict:
    """
    Best single calendar day Core revenue among scoped stores (TotalCore daily rows).
    Historical months still use TotalCore daily in-range; avoids monthly-financial rollup for this intent.
    """
    _, scope_key = _retail_scope_filter(scope)
    cap = max(1, min(int(top_pairs), 25))
    obj_name = _validated_this_month_revenue_object()
    cat = (Config.SQL_SALES_CORE_CATEGORY or "").strip()
    filter_notes: List[str] = ["retail locations: store + outlet"] if scope_key == "all_retail_stores" else []
    if cat:
        filter_notes.append(f"Category/RevenueType = {cat}")

    idx = _scoped_location_index(scope)
    by_store_day = _network_revenue_by_store_day(scope, start_date, end_date)
    candidates: List[dict] = []
    for sid, days in by_store_day.items():
        name = idx[sid].get("LocationName") if sid in idx else None
        for dk, v in days.items():
            candidates.append({
                "location_id": sid,
                "location_name": name,
                "date": dk,
                "metric_value": round(v, 2),
            })

    candidates.sort(key=lambda x: x["metric_value"], reverse=True)
    top = candidates[:cap]

    tf = {"start": start_date, "end": end_date}
    if timeframe_label:
        tf["label"] = timeframe_label

    return {
        "metric": "revenue",
        "grain": "single_store_day_peak",
        "scope": scope_key,
        "timeframe": tf,
        "leader": top[0] if top else None,
        "top_store_days": top,
        "source": {
            "name": obj_name,
            "grain": "daily",
            "metric": "NetRevenue per store per SalesDate",
            "date_range": f"{start_date} to {end_date}",
            "filters": filter_notes,
        },
    }


def get_revenue_door_count_series(
    store_id: str,
    start_date: str,
    end_date: str,
    *,
    grain: str = "day",
    today: Optional[date] = None,
) -> dict:
    """Aligned revenue + door count series for one store (daily or monthly buckets)."""
    current_day = today or date.today()
    store_id = str(store_id).strip()
    loc = resolve_location_reference(store_id)
    if not loc:
        return {"error": "unknown_store", "series": [], "grain": grain}

    lid = str(loc["LocationID"])
    use_daily_revenue = _is_current_month_timeframe(start_date, end_date, current_day)
    fin = get_financials(lid, start_date, end_date, this_month=use_daily_revenue)
    doors = get_door_count(lid, start_date, end_date)

    if (grain or "day").lower() == "month":
        buckets = {}
        for row in fin:
            sd = row.get("SalesDate") or row.get("PeriodMonth")
            if sd is None:
                continue
            dk = sd.isoformat()[:7] if hasattr(sd, "isoformat") else str(sd)[:7]
            buckets.setdefault(dk, {"revenue": 0.0, "doors": 0.0})
            buckets[dk]["revenue"] += _coerce_number(row.get("NetRevenue"))
        for row in doors:
            cd = row.get("CountDate")
            if cd is None:
                continue
            dk = cd.isoformat()[:7] if hasattr(cd, "isoformat") else str(cd)[:7]
            buckets.setdefault(dk, {"revenue": 0.0, "doors": 0.0})
            buckets[dk]["doors"] += _coerce_number(row.get("DonorVisits"))
        series_keys = sorted(buckets.keys())
        series = []
        for k in series_keys:
            r = buckets[k]["revenue"]
            d = buckets[k]["doors"]
            series.append({
                "period": k,
                "revenue": round(r, 2),
                "door_count": int(round(d)),
                "revenue_per_visit": round(r / d, 4) if d > 0 else None,
            })
        g = "month"
    else:
        by_day = {}
        for row in fin:
            sd = row.get("SalesDate")
            if sd is None:
                continue
            dk = sd.isoformat()[:10] if hasattr(sd, "isoformat") else str(sd)[:10]
            by_day.setdefault(dk, {"revenue": 0.0, "doors": 0.0})
            by_day[dk]["revenue"] += _coerce_number(row.get("NetRevenue"))
        for row in doors:
            cd = row.get("CountDate")
            if cd is None:
                continue
            dk = cd.isoformat()[:10] if hasattr(cd, "isoformat") else str(cd)[:10]
            by_day.setdefault(dk, {"revenue": 0.0, "doors": 0.0})
            by_day[dk]["doors"] += _coerce_number(row.get("DonorVisits"))
        series_keys = sorted(by_day.keys())
        series = []
        for k in series_keys:
            r = by_day[k]["revenue"]
            d = by_day[k]["doors"]
            series.append({
                "date": k,
                "revenue": round(r, 2),
                "door_count": int(round(d)),
                "revenue_per_visit": round(r / d, 4) if d > 0 else None,
            })
        g = "day"

    return {
        "location_id": lid,
        "location_name": loc.get("LocationName"),
        "grain": g,
        "timeframe": {"start": start_date, "end": end_date},
        "series": series,
        "source": {
            "revenue_table": _validated_this_month_revenue_object() if use_daily_revenue else _validated_retail_monthly_financial_object(),
            "door_table": _validated_door_count_object(),
            "note": "Revenue grain follows current-month TotalCore vs monthly summary rules.",
        },
    }


def network_correlation_revenue_door(
    start_date: str,
    end_date: str,
    *,
    scope: str = "all_retail_stores",
    timeframe_label: Optional[str] = None,
) -> dict:
    """Daily summed revenue vs summed door counts across scoped locations; Pearson r on overlapping days."""
    by_rev: Dict[str, float] = {}
    for store_days in _network_revenue_by_store_day(scope, start_date, end_date).values():
        for dk, v in store_days.items():
            by_rev[dk] = by_rev.get(dk, 0.0) + v

    by_door: Dict[str, float] = {}
    for store_days in _network_door_by_store_day(scope, start_date, end_date).values():
        for dk, v in store_days.items():
            by_door[dk] = by_door.get(dk, 0.0) + v

    days = sorted(set(by_rev.keys()) & set(by_door.keys()))
    xs = [by_rev[d] for d in days]
    ys = [by_door[d] for d in days]
    n = len(xs)
    pearson_r = None
    if n >= 3:
        mx = sum(xs) / n
        my = sum(ys) / n
        vx = sum((x - mx) ** 2 for x in xs)
        vy = sum((y - my) ** 2 for y in ys)
        if vx > 1e-9 and vy > 1e-9:
            pearson_r = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / math.sqrt(vx * vy)

    _, scope_key = _retail_scope_filter(scope)
    tf = {"start": start_date, "end": end_date}
    if timeframe_label:
        tf["label"] = timeframe_label

    return {
        "intent": "correlation_check",
        "metric_pair": ["network_revenue", "network_door_count"],
        "grain": "day",
        "scope": scope_key,
        "timeframe": tf,
        "overlap_days": n,
        "pearson_r": None if pearson_r is None else round(float(pearson_r), 4),
        "series": [{"date": d, "network_revenue": round(by_rev[d], 2), "network_door_count": int(round(by_door[d]))} for d in days],
        "source": {
            "revenue": _validated_this_month_revenue_object(),
            "door_count": _validated_door_count_object(),
            "filters": ["summed across scoped locations"],
        },
    }


def aggregate_network_metric(
    metric: str,
    start_date: str,
    end_date: str,
    *,
    scope: str = "all_retail_stores",
    today: Optional[date] = None,
) -> float:
    """Total metric across scoped locations for one date range."""
    current_day = today or date.today()
    if metric == "revenue":
        rev_map = _network_revenue_by_store_day(scope, start_date, end_date)
        return sum(sum(days.values()) for days in rev_map.values())
    if metric == "door_count":
        door_map = _network_door_by_store_day(scope, start_date, end_date)
        return sum(sum(days.values()) for days in door_map.values())
    if metric == "donations":
        don_map = _network_donations_by_store_day(scope, start_date, end_date)
        return sum(sum(days.values()) for days in don_map.values())
    total = 0.0
    for _lid, _name, val in _parallel_store_metric_totals(
        _iterate_scoped_locations(scope), metric, start_date, end_date, current_day
    ):
        total += val
    return total


def aggregate_network_expense_ratio(
    start_date: str,
    end_date: str,
    *,
    scope: str = "all_retail_stores",
    today: Optional[date] = None,
) -> float:
    """Network-wide (operating+personnel) / revenue from monthly financial rows."""
    def _work(loc):
        lid = str(loc["LocationID"])
        rows = get_financials(lid, start_date, end_date, this_month=False)
        return _sum_field(rows, "NetRevenue"), _sum_field(rows, "OperatingExpenses")

    total_rev = 0.0
    total_opex = 0.0
    for rev, opex in _parallel_map(_work, _iterate_scoped_locations(scope)):
        total_rev += rev
        total_opex += opex
    if total_rev <= 1e-9:
        return 0.0
    return total_opex / total_rev


def compare_period_totals(
    metric: str,
    timeframe_a: dict,
    timeframe_b: dict,
    *,
    scope: str = "all_retail_stores",
    today: Optional[date] = None,
) -> dict:
    """Compare network-wide aggregates between two ranges (no LLM SQL)."""
    current_day = today or date.today()
    a_start, a_end = timeframe_a["start"], timeframe_a["end"]
    b_start, b_end = timeframe_b["start"], timeframe_b["end"]

    mapped = metric if metric != "revenue" else "revenue"
    if mapped == "expense_ratio":
        val_a = aggregate_network_expense_ratio(a_start, a_end, scope=scope, today=current_day)
        val_b = aggregate_network_expense_ratio(b_start, b_end, scope=scope, today=current_day)
    else:
        val_a = aggregate_network_metric(mapped, a_start, a_end, scope=scope, today=current_day)
        val_b = aggregate_network_metric(mapped, b_start, b_end, scope=scope, today=current_day)

    pct = None
    if val_b != 0:
        pct = round(100.0 * (val_a - val_b) / abs(val_b), 2)

    _, scope_key = _retail_scope_filter(scope)
    return {
        "intent": "compare_periods",
        "metric": mapped,
        "scope": scope_key,
        "period_a": {"timeframe": timeframe_a, "value": round(val_a, 2) if mapped != "expense_ratio" else round(val_a, 4)},
        "period_b": {"timeframe": timeframe_b, "value": round(val_b, 2) if mapped != "expense_ratio" else round(val_b, 4)},
        "pct_change_vs_b": pct,
        "source": {"note": "Network sum across scoped locations using approved queries."},
    }


def revenue_per_visit_by_store(
    start_date: str,
    end_date: str,
    *,
    scope: str = "all_retail_stores",
    limit: int = 15,
    today: Optional[date] = None,
) -> dict:
    """Derived ranking: TotalRevenue / TotalDonorVisits per location for range."""
    cap = max(1, min(int(limit), 25))
    idx = _scoped_location_index(scope)
    rev_map = _network_revenue_by_store_day(scope, start_date, end_date)
    door_map = _network_door_by_store_day(scope, start_date, end_date)
    ranked_list = []
    for sid, loc in idx.items():
        rev = sum(rev_map.get(sid, {}).values())
        doors = sum(door_map.get(sid, {}).values())
        rpv = rev / doors if doors > 0 else None
        ranked_list.append({
            "location_id": sid,
            "location_name": loc.get("LocationName"),
            "revenue": round(rev, 2),
            "door_count": int(round(doors)),
            "revenue_per_visit": None if rpv is None else round(rpv, 4),
        })
    filtered = [r for r in ranked_list if r["revenue_per_visit"] is not None]
    filtered.sort(key=lambda x: x["revenue_per_visit"], reverse=True)
    filtered = filtered[:cap]

    _, scope_key = _retail_scope_filter(scope)
    return {
        "intent": "derived_metric",
        "derived": "revenue_per_visit",
        "scope": scope_key,
        "timeframe": {"start": start_date, "end": end_date},
        "locations": filtered,
        "source": {"name": "TotalCore + PCounter rollup", "metric": "revenue per donor visit"},
    }


def trend_summary_for_chat(
    store_id: str,
    months: int = 12,
) -> dict:
    """Thin wrapper around get_trends for grounded chat payloads."""
    rows = get_trends(store_id, max(1, min(int(months), 240)))
    loc = resolve_location_reference(store_id)
    return {
        "intent": "trend_summary",
        "granularity": "month",
        "months_requested": months,
        "location_id": str(store_id),
        "location_name": loc.get("LocationName") if loc else None,
        "rows": rows,
        "source": {
            "financial": _validated_retail_monthly_financial_object(),
            "door": _validated_door_count_object(),
            "grain": "month",
            "note": "Monthly rollup for the requested month span (includes current month when in range).",
        },
    }


def multi_metric_snapshot(
    store_id: str,
    start_date: str,
    end_date: str,
    *,
    today: Optional[date] = None,
) -> dict:
    """Revenue-related monthly financials plus door totals for one store."""
    loc = resolve_location_reference(store_id)
    if not loc:
        return {"error": "unknown_store"}

    lid = str(loc["LocationID"])
    mrows = get_financials(lid, start_date, end_date, this_month=False)
    metrics = {
        "net_revenue": round(_sum_field(mrows, "NetRevenue"), 2),
        "net_income": round(_sum_field(mrows, "NetIncome"), 2),
        "operating_expenses": round(_sum_field(mrows, "OperatingExpenses"), 2),
        "personnel_expenses": round(_sum_field(mrows, "TotalPersonnelExpenses"), 2),
        "expense_ratio_avg": round(
            sum(_coerce_number(r.get("ExpenseRatio")) for r in mrows if r.get("ExpenseRatio") is not None)
            / max(1, len([r for r in mrows if r.get("ExpenseRatio") is not None])),
            4,
        ) if mrows else None,
        "door_count_total": int(round(_sum_field(get_door_count(lid, start_date, end_date), "DonorVisits"))),
    }

    return {
        "intent": "multi_metric_summary",
        "location_id": lid,
        "location_name": loc.get("LocationName"),
        "timeframe": {"start": start_date, "end": end_date},
        "metrics": metrics,
        "source": {
            "monthly_financial": _validated_retail_monthly_financial_object(),
            "door_daily": _validated_door_count_object(),
        },
    }


def donor_map_summary(store_id: str, max_sample: int = 5) -> dict:
    """Light donor geography summary for analytics chat (counts only; no dumping full KML here)."""
    rows = get_donor_addresses(store_id)
    loc = resolve_location_reference(store_id)
    sample_states = []
    for row in rows[:max_sample]:
        st = row.get("State")
        if st:
            sample_states.append(str(st).strip())

    cities = []
    seen = set()
    for row in rows[:50]:
        c = row.get("City")
        key = str(c).strip().lower() if c else ""
        if key and key not in seen:
            seen.add(key)
            cities.append(str(c).strip())
        if len(cities) >= 5:
            break

    return {
        "intent": "map_context_summary",
        "location_id": str(store_id),
        "location_name": loc.get("LocationName") if loc else None,
        "donor_pins_returned_by_query": len(rows),
        "sample_states": sorted(set(sample_states)),
        "sample_cities_preview": cities,
        "source": {"table": "dbo.DonorAddresses", "grain": "point-level (aggregated counts only)"},
    }


def build_data_catalog() -> dict:
    """Metadata-only capability list for assistants (no database reads)."""
    try:
        from ai.question_bank import load_question_bank, sample_questions_for_catalog

        bank = load_question_bank()
        examples = sample_questions_for_catalog(24)
        bank_total = int(bank.get("total") or 0)
    except Exception:
        examples = []
        bank_total = 0

    return {
        "intent": "data_catalog",
        "version": "2",
        "description": (
            "GWSA GeoAnalytics chat uses approved parameterized queries only. "
            "Intents include store summaries, rankings, trends, correlations, period compares, "
            "breakdowns by store, revenue category breakdowns (Category/RevenueType), "
            "derived revenue-per-visit, donor map counts, donation totals, "
            "and actual vs budget core revenue. Follow-up questions can reuse stores and dates "
            "from the prior turn when you say things like 'show categories' or 'add door count'."
        ),
        "example_questions": examples,
        "question_bank_size": bank_total,
        "datasets": [
            {"name": _validated_this_month_revenue_object(), "grain": "daily_core_revenue"},
            {"name": _validated_retail_monthly_financial_object(), "grain": "monthly_financials"},
            {"name": _validated_door_count_object(), "grain": "daily_door_visits"},
            {"name": _validated_donations_object(), "grain": "daily_donation_amounts"},
            {"name": _validated_budget_vs_actual_object(), "grain": "daily_actual_vs_budget_core"},
            {"name": "dbo.DonorAddresses", "grain": "donor_latitude_longitude"},
        ],
        "metrics": [
            "revenue (core sales)",
            "door_count / donor visits",
            "donations (DonationAmt from tbl_Donation)",
            "actual vs budget core revenue (variance and % of budget)",
            "net income, operating expenses, personnel expenses, expense ratio (monthly summary)",
            "revenue_per_visit derived",
            "network correlation revenue vs visits (daily summed)",
            "trends: multi-month revenue, net income, expense ratio with door counts",
            "category_breakdown: Sub_Category breakdown from TotalCoreTableFinal (sums to Core Sales for the period)",
        ],
    }
