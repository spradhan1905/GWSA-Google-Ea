"""
GWSA GeoAnalytics — Configuration
Loads from .env via python-dotenv.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Always load backend/.env regardless of cwd (Flask often runs from repo root).
_backend_dir = Path(__file__).resolve().parent
load_dotenv(_backend_dir / ".env")
load_dotenv()  # optional: cwd .env overrides for local experiments


class Config:
    # SQL Server
    SQL_SERVER   = os.environ.get('SQL_SERVER', 'localhost')
    SQL_DATABASE = os.environ.get('SQL_DATABASE', 'GWSA_Analytics')
    SQL_USERNAME = os.environ.get('SQL_USERNAME', '')
    SQL_PASSWORD = os.environ.get('SQL_PASSWORD', '')
    SQL_DRIVER   = os.environ.get('SQL_DRIVER', '{ODBC Driver 17 for SQL Server}')
    SQL_ENCRYPT = os.environ.get('SQL_ENCRYPT', 'yes').strip()
    SQL_TRUST_SERVER_CERTIFICATE = os.environ.get('SQL_TRUST_SERVER_CERTIFICATE', 'yes').strip()
    # True = Trusted Connection / Windows Integrated Security (no SQL login; app must run as a Windows user allowed on SQL)
    SQL_USE_WINDOWS_AUTH = os.environ.get('SQL_USE_WINDOWS_AUTH', 'False').lower() == 'true'
    # Line-level sales (daily POS). Full three-part name, e.g. JS_API.dbo.SalesFactFinal (legacy / other uses).
    SQL_SALES_LINE_OBJECT = os.environ.get('SQL_SALES_LINE_OBJECT', 'JS_API.dbo.SalesFactFinal')
    # This Month MTD revenue: JS_API.dbo.TotalCoreTableFinal — [Unit] encodes location (e.g. 20-10-129-12000 → 129).
    SQL_THIS_MONTH_REVENUE_OBJECT = os.environ.get(
        'SQL_THIS_MONTH_REVENUE_OBJECT', 'JS_API.dbo.TotalCoreTableFinal'
    ).strip()
    # Quarter / YTD / 12 Months: monthly store rollup (Unit Name matches static LocationName / DB Locations).
    SQL_RETAIL_MONTHLY_FINANCIAL_OBJECT = os.environ.get(
        'SQL_RETAIL_MONTHLY_FINANCIAL_OBJECT', 'JS_API.dbo.RetailStoreMonthlyFinancialSummary'
    ).strip()
    # Locations: "static" = backend/db/static_locations.py (no dbo.Locations table). "database" = SQL_LOCATIONS_TABLE in SQL.
    LOCATIONS_SOURCE = os.environ.get('LOCATIONS_SOURCE', 'static').strip().lower()
    # Used only when LOCATIONS_SOURCE=database
    SQL_LOCATIONS_TABLE = os.environ.get('SQL_LOCATIONS_TABLE', 'dbo.Locations')
    # This Month: must match TotalCoreTableFinal.[Category] OR [RevenueType]. Empty = no category filter.
    SQL_SALES_CORE_CATEGORY = os.environ.get('SQL_SALES_CORE_CATEGORY', 'Core Sales')
    # When true, match [sales unit name] if it equals our name OR either string contains the other (GP vs app naming).
    SQL_SALES_UNIT_NAME_FLEXIBLE = os.environ.get('SQL_SALES_UNIT_NAME_FLEXIBLE', 'True').lower() == 'true'
    # True = join only on LocationName + numeric LocationID (no extra columns on Locations). Default True until migration.
    # After models/migrations/001_locations_add_sales_keys.sql and populating keys, set False for full GP matching.
    SQL_LOCATIONS_MINIMAL_JOIN = os.environ.get('SQL_LOCATIONS_MINIMAL_JOIN', 'True').lower() == 'true'
    # Door counts: three-part name, e.g. PeopleCounter.dbo.PCounter (see SQL_DOOR_COUNT_COL_*).
    SQL_DOOR_COUNT_OBJECT = os.environ.get('SQL_DOOR_COUNT_OBJECT', 'PeopleCounter.dbo.PCounter').strip()
    # PCounter uses [Date] (daily grain is rolled up from hourly rows in SQL).
    SQL_DOOR_COUNT_COL_DATE = os.environ.get('SQL_DOOR_COUNT_COL_DATE', 'Date').strip()
    SQL_DOOR_COUNT_COL_VISITS = os.environ.get('SQL_DOOR_COUNT_COL_VISITS', 'In').strip()
    SQL_DOOR_COUNT_COL_LOCATION = os.environ.get('SQL_DOOR_COUNT_COL_LOCATION', 'LocationID').strip()

    # Gemini AI
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

    # Flask
    SECRET_KEY  = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-change-in-production')
    CORS_ORIGIN = os.environ.get('CORS_ORIGIN', 'http://localhost:5173')
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.environ.get('CORS_ORIGINS', CORS_ORIGIN).split(',')
        if origin.strip()
    ]
    DEBUG       = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    FORCE_HTTPS = os.environ.get('FORCE_HTTPS', 'False').lower() == 'true'
