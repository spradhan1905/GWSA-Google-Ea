-- ============================================
-- Sage + legacy monthly financial merge (reference)
-- ============================================
-- The GeoAnalytics API merges these sources in application code when
-- SQL_SAGE_MERGE_ENABLED=True (default). Run this script only if you prefer
-- a database view instead of in-app merge (then set SQL_SAGE_MERGE_ENABLED=False
-- and SQL_RETAIL_MONTHLY_FINANCIAL_OBJECT to the view name below).
--
-- Cutover: 2026-07-01 (Sage starts; legacy through June 2026).

USE JS_API;
GO

-- Optional: tune glAccount_id → P&L bucket mapping for your chart of accounts.
IF OBJECT_ID('dbo.GL_Account_Metric_Map', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.GL_Account_Metric_Map (
        glAccount_id INT NOT NULL PRIMARY KEY,
        Metric       VARCHAR(20) NOT NULL  -- Revenue | OpEx | Personnel
    );
    INSERT INTO dbo.GL_Account_Metric_Map (glAccount_id, Metric) VALUES
        (60000, 'OpEx'),
        (60001, 'OpEx');
    -- Extend with finance-approved account ids / ranges.
END
GO

-- Validation: no overlapping months between legacy and Sage sides
-- SELECT [Year], [Month], [Unit Name], COUNT(*) FROM dbo.RetailStoreMonthlyFinancialSummary_Merged
-- GROUP BY [Year], [Month], [Unit Name] HAVING COUNT(*) > 1;
