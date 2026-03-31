-- Run in SSMS against JS_API (or your database).
-- SQL Server does NOT allow "SELECT TOP 50 DISTINCT ..." — use DISTINCT before TOP.

-- 1) Distinct category + store name (correct syntax)
SELECT DISTINCT TOP 200
    LTRIM(RTRIM(CAST(SalesCategoryFromGP AS NVARCHAR(200)))) AS SalesCategoryFromGP,
    LTRIM(RTRIM(CAST([sales unit name] AS NVARCHAR(500))))    AS sales_unit_name
FROM dbo.SalesFactFinal
ORDER BY sales_unit_name;

-- 2) What does Soldts look like? (raw + converted calendar date)
SELECT TOP 20
    Soldts,
    SQL_VARIANT_PROPERTY(Soldts, 'BaseType') AS base_type,
    CAST(TRY_CONVERT(DATETIME, Soldts) AS DATE) AS sale_date
FROM dbo.SalesFactFinal
ORDER BY TRY_CONVERT(DATETIME, Soldts) DESC;

-- 3) Row counts by calendar month (uses same date logic as the API)
SELECT
    YEAR(CAST(TRY_CONVERT(DATETIME, Soldts) AS DATE))  AS y,
    MONTH(CAST(TRY_CONVERT(DATETIME, Soldts) AS DATE)) AS m,
    COUNT(*) AS row_count,
    SUM(ISNULL(CAST(Revenue AS DECIMAL(18, 4)), 0)) AS sum_revenue
FROM dbo.SalesFactFinal
WHERE TRY_CONVERT(DATETIME, Soldts) IS NOT NULL
GROUP BY
    YEAR(CAST(TRY_CONVERT(DATETIME, Soldts) AS DATE)),
    MONTH(CAST(TRY_CONVERT(DATETIME, Soldts) AS DATE))
ORDER BY y DESC, m DESC;

-- 4) One store, one month — same filters as the API (replace @start, @end, @unit from query 1)
DECLARE @start DATE = '2026-03-01';
DECLARE @end   DATE = '2026-03-30';
DECLARE @unit  NVARCHAR(500) = N'Commerce Retail Store';  -- exact [sales unit name] from query 1

SELECT
    CAST(TRY_CONVERT(DATETIME, Soldts) AS DATE) AS sale_day,
    SUM(ISNULL(CAST(Revenue AS DECIMAL(18, 4)), 0)) AS daily_revenue
FROM dbo.SalesFactFinal
WHERE TRY_CONVERT(DATETIME, Soldts) IS NOT NULL
  AND CAST(TRY_CONVERT(DATETIME, Soldts) AS DATE) >= @start
  AND CAST(TRY_CONVERT(DATETIME, Soldts) AS DATE) <= @end
  AND LTRIM(RTRIM(CAST([sales unit name] AS NVARCHAR(500)))) COLLATE Latin1_General_CI_AI
      = LTRIM(RTRIM(@unit)) COLLATE Latin1_General_CI_AI
GROUP BY CAST(TRY_CONVERT(DATETIME, Soldts) AS DATE)
ORDER BY sale_day;
