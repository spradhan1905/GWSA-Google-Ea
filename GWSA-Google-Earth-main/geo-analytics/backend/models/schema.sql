-- ============================================
-- GWSA GeoAnalytics — SQL Server Schema
-- Goodwill Industries of San Antonio
-- ============================================

CREATE TABLE dbo.Locations (
    LocationID      VARCHAR(50)   PRIMARY KEY,
    LocationName    NVARCHAR(100) NOT NULL,
    LocationType    VARCHAR(20)   NOT NULL
        CONSTRAINT CK_LocationType CHECK (LocationType IN ('store','adc','outlet','dropbox')),
    -- Optional keys to match JS_API.dbo.SalesFactFinal (see sample_sales_file.xlsx / SoldStoreId, sales store unit)
    SoldStoreId     INT           NULL,
    SalesStoreUnit  NVARCHAR(120) NULL,
    Manager         NVARCHAR(100),
    Latitude        DECIMAL(9,6),
    Longitude       DECIMAL(9,6),
    IsActive        BIT           DEFAULT 1,
    CreatedAt       DATETIME      DEFAULT GETDATE()
);
CREATE INDEX IX_Locations_SoldStoreId ON dbo.Locations (SoldStoreId) WHERE SoldStoreId IS NOT NULL;

CREATE TABLE dbo.Financials (
    FinancialID     INT IDENTITY  PRIMARY KEY,
    LocationID      VARCHAR(50)   NOT NULL REFERENCES dbo.Locations(LocationID),
    PeriodMonth     DATE          NOT NULL,
    NetRevenue      DECIMAL(12,2),
    NetIncome       DECIMAL(12,2),
    ExpenseRatio    DECIMAL(5,4),
    DonatedGoodsRev DECIMAL(12,2),
    RetailRevenue   DECIMAL(12,2),
    UpdatedAt       DATETIME      DEFAULT GETDATE(),
    CONSTRAINT UQ_Financials_Loc_Month UNIQUE (LocationID, PeriodMonth)
);
CREATE INDEX IX_Financials_Loc_Period ON dbo.Financials (LocationID, PeriodMonth);

-- Optional local/dev mirror. Production door metrics read PeopleCounter.dbo.PCounter (see backend SQL_DOOR_COUNT_* env).
CREATE TABLE dbo.DoorCount (
    DoorCountID     INT IDENTITY  PRIMARY KEY,
    LocationID      VARCHAR(50)   NOT NULL REFERENCES dbo.Locations(LocationID),
    CountDate       DATE          NOT NULL,
    DonorVisits     INT           NOT NULL DEFAULT 0,
    UpdatedAt       DATETIME      DEFAULT GETDATE(),
    CONSTRAINT UQ_DoorCount_Loc_Date UNIQUE (LocationID, CountDate)
);
CREATE INDEX IX_DoorCount_Loc_Date ON dbo.DoorCount (LocationID, CountDate);

CREATE TABLE dbo.DonorAddresses (
    DonorID         INT IDENTITY  PRIMARY KEY,
    LocationID      VARCHAR(50)   REFERENCES dbo.Locations(LocationID),
    Address1        NVARCHAR(200),
    City            NVARCHAR(100),
    State           CHAR(2),
    Zip             VARCHAR(10),
    Latitude        DECIMAL(9,6),
    Longitude       DECIMAL(9,6),
    KmlLayer        VARCHAR(100)
);

-- Read-only app user (run as SA/admin)
CREATE LOGIN gwsa_app_user WITH PASSWORD = 'CHANGE_THIS_PASSWORD!';
CREATE USER  gwsa_app_user FOR LOGIN gwsa_app_user;
GRANT SELECT ON dbo.Locations      TO gwsa_app_user;
GRANT SELECT ON dbo.Financials     TO gwsa_app_user;
GRANT SELECT ON dbo.DoorCount      TO gwsa_app_user;
GRANT SELECT ON dbo.DonorAddresses TO gwsa_app_user;
