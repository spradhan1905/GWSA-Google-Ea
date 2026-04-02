/*
  Diagnose JS_API.dbo.TotalCoreTableFinal when MTD / app shows $0 or SSMS returns 0 rows for "this month".

  Run in SSMS (steps 1–4, then 5–7 after GO). If step 1 has cnt = 0, the table is empty or the name/schema is wrong.
  If step 2 latest_date is before the first day of the current month, (5)/(6) will be empty — that is expected until ETL loads.

  Note: For zero matching rows, SUM(Revenue) is NULL in SQL; this script uses ISNULL(...,0) in (5)/(6) so you see 0 not NULL.
*/
SET NOCOUNT ON;

-- 1) Any rows at all?
SELECT COUNT(*) AS row_count
FROM JS_API.dbo.TotalCoreTableFinal;

-- 2) What date range exists?
SELECT
    MIN(CAST([Date] AS date)) AS earliest_date,
    MAX(CAST([Date] AS date)) AS latest_date
FROM JS_API.dbo.TotalCoreTableFinal;

-- 3) Latest rows (see Unit, Category, RevenueType, Revenue)
SELECT TOP 25
    CAST([Date] AS date) AS [Date],
    [Revenue],
    [Unit],
    [sales unit name],
    [Category],
    [RevenueType]
FROM JS_API.dbo.TotalCoreTableFinal
ORDER BY CAST([Date] AS date) DESC, [Unit];

-- 4) Row counts by calendar month (last 14 months)
SELECT
    YEAR(CAST([Date] AS date)) AS y,
    MONTH(CAST([Date] AS date)) AS m,
    COUNT(*) AS row_count,
    SUM(CAST([Revenue] AS decimal(18, 4))) AS sum_revenue
FROM JS_API.dbo.TotalCoreTableFinal
WHERE CAST([Date] AS date) >= DATEADD(MONTH, -14, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
GROUP BY YEAR(CAST([Date] AS date)), MONTH(CAST([Date] AS date))
ORDER BY y DESC, m DESC;

GO
/*
  Steps 5–7 use variables. GO starts a new batch (required in SSMS so DECLARE is valid).
*/
DECLARE @start date = DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1);
DECLARE @end   date = CAST(GETDATE() AS date);
DECLARE @latest date =
    (SELECT MAX(CAST([Date] AS date)) FROM JS_API.dbo.TotalCoreTableFinal);
DECLARE @month_of_latest_start date =
    CASE WHEN @latest IS NULL THEN NULL
         ELSE DATEFROMPARTS(YEAR(@latest), MONTH(@latest), 1) END;

-- 5) Same filter as the app: current calendar month to date (SQL Server clock: GETDATE())
--    If mtd_row_count = 0, mtd_sum_revenue shows 0 here (ISNULL). Raw SUM of zero rows is NULL in SQL.
SELECT
    @start AS range_start,
    @end   AS range_end,
    COUNT(*) AS mtd_row_count,
    ISNULL(SUM(CAST([Revenue] AS decimal(18, 4))), 0) AS mtd_sum_revenue
FROM JS_API.dbo.TotalCoreTableFinal
WHERE CAST([Date] AS date) >= @start
  AND CAST([Date] AS date) <= @end;

-- 5b) Why (5)/(6) can be empty: compare "today" on this server to the latest [Date] in the table
SELECT
    CAST(GETDATE() AS datetime2(0)) AS sql_server_now,
    CAST(GETDATE() AS date)         AS sql_server_today,
    @start                          AS current_month_start,
    (SELECT MAX(CAST([Date] AS date)) FROM JS_API.dbo.TotalCoreTableFinal) AS latest_date_in_table,
    CASE
        WHEN (SELECT MAX(CAST([Date] AS date)) FROM JS_API.dbo.TotalCoreTableFinal) IS NULL THEN
            N'Table has no rows — check database/schema/object name.'
        WHEN (SELECT MAX(CAST([Date] AS date)) FROM JS_API.dbo.TotalCoreTableFinal) < @start THEN
            N'Latest [Date] is BEFORE the first day of the current month — this month''s data is not loaded yet (or ETL is behind).'
        ELSE
            N'Latest [Date] is in the current month — if (5) is still 0, inspect [Date] values (type/format) or filters.'
    END AS interpretation;

-- 6) Same date range as (5) plus Core-style filter (match backend .env SQL_SALES_CORE_CATEGORY, default Core Sales)
SELECT
    COUNT(*) AS mtd_core_row_count,
    ISNULL(SUM(CAST([Revenue] AS decimal(18, 4))), 0) AS mtd_core_sum_revenue
FROM JS_API.dbo.TotalCoreTableFinal
WHERE CAST([Date] AS date) >= @start
  AND CAST([Date] AS date) <= @end
  AND (
      LTRIM(RTRIM(CAST([Category] AS nvarchar(200)))) COLLATE Latin1_General_CI_AI
          = LTRIM(RTRIM(N'Core Sales')) COLLATE Latin1_General_CI_AI
      OR LTRIM(RTRIM(CAST([RevenueType] AS nvarchar(200)))) COLLATE Latin1_General_CI_AI
          = LTRIM(RTRIM(N'Core Sales')) COLLATE Latin1_General_CI_AI
  );

-- 7) Totals for the calendar month that contains MAX([Date]) — use when (5)/(6) are empty but step 2 shows a latest_date
SELECT
    @latest              AS latest_date_in_table,
    @month_of_latest_start AS first_day_of_that_month,
    (SELECT COUNT(*)
     FROM JS_API.dbo.TotalCoreTableFinal
     WHERE @latest IS NOT NULL
       AND CAST([Date] AS date) >= @month_of_latest_start
       AND CAST([Date] AS date) <= @latest) AS rows_in_month_of_latest_date,
    ISNULL((
        SELECT SUM(CAST([Revenue] AS decimal(18, 4)))
        FROM JS_API.dbo.TotalCoreTableFinal
        WHERE @latest IS NOT NULL
          AND CAST([Date] AS date) >= @month_of_latest_start
          AND CAST([Date] AS date) <= @latest
    ), 0) AS sum_revenue_month_of_latest_date;
