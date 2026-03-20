"""
GWSA GeoAnalytics — Database Connection
SQL Server via pyodbc with connection pooling.
"""
import pyodbc
from config import Config


def get_connection():
    """Create a SQL Server connection using config values."""
    conn_str = (
        f"DRIVER={Config.SQL_DRIVER};"
        f"SERVER={Config.SQL_SERVER};"
        f"DATABASE={Config.SQL_DATABASE};"
        f"UID={Config.SQL_USERNAME};"
        f"PWD={Config.SQL_PASSWORD};"
        "TrustServerCertificate=yes;"
        "Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str)


def test_connection() -> bool:
    """Quick health check for the database."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB] Connection failed: {e}")
        return False
