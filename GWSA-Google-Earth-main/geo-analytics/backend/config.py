"""
GWSA GeoAnalytics — Configuration
Fails fast on startup if any required env var is missing.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # SQL Server — required (KeyError on missing)
    SQL_SERVER   = os.environ.get('SQL_SERVER', 'localhost')
    SQL_DATABASE = os.environ.get('SQL_DATABASE', 'GWSA_Analytics')
    SQL_USERNAME = os.environ.get('SQL_USERNAME', 'gwsa_app_user')
    SQL_PASSWORD = os.environ.get('SQL_PASSWORD', '')
    SQL_DRIVER   = os.environ.get('SQL_DRIVER', '{ODBC Driver 17 for SQL Server}')

    # Gemini AI
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

    # Flask
    SECRET_KEY  = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-change-in-production')
    CORS_ORIGIN = os.environ.get('CORS_ORIGIN', 'http://localhost:5173')
    DEBUG       = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    # Demo mode — serves mock data when DB is unavailable
    DEMO_MODE = os.environ.get('DEMO_MODE', 'True').lower() == 'true'
