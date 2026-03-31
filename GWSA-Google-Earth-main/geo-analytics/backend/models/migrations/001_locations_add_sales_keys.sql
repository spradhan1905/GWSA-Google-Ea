-- Add GP / sales-fact join keys to Locations (ties app locations to SalesFactFinal).
-- Run once on existing JS_API (or your app) database. Safe if columns already exist: skip or adjust.

IF COL_LENGTH('dbo.Locations', 'SoldStoreId') IS NULL
BEGIN
    ALTER TABLE dbo.Locations ADD SoldStoreId INT NULL;
END
GO

IF COL_LENGTH('dbo.Locations', 'SalesStoreUnit') IS NULL
BEGIN
    ALTER TABLE dbo.Locations ADD SalesStoreUnit NVARCHAR(120) NULL;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes WHERE name = 'IX_Locations_SoldStoreId' AND object_id = OBJECT_ID('dbo.Locations')
)
BEGIN
    CREATE INDEX IX_Locations_SoldStoreId ON dbo.Locations (SoldStoreId) WHERE SoldStoreId IS NOT NULL;
END
GO
