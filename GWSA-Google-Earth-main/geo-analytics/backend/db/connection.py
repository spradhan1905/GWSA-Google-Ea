"""
GWSA GeoAnalytics — Database Connection
SQL Server via pyodbc with connection pooling.
pyodbc is imported lazily so the app can start before first DB access.
"""
from config import Config

_pyodbc = None


def _get_pyodbc():
    global _pyodbc
    if _pyodbc is None:
        try:
            import pyodbc
            _pyodbc = pyodbc
        except ImportError:
            raise RuntimeError(
                "pyodbc is not installed. Install it with: pip install pyodbc\n"
                "This is required for live SQL queries."
            )
    return _pyodbc


def get_connection():
    """Create a SQL Server connection using config values."""
    pyodbc = _get_pyodbc()
    if not Config.SQL_USE_WINDOWS_AUTH and (
        not (Config.SQL_USERNAME or "").strip() or not (Config.SQL_PASSWORD or "").strip()
    ):
        raise RuntimeError(
            "SQL login requires SQL_USERNAME and SQL_PASSWORD in the environment. "
            "On Render/Linux, Windows Integrated Security is not available—use a SQL Server login "
            "(set SQL_USE_WINDOWS_AUTH=false or omit it). On Windows dev only, you may use "
            "SQL_USE_WINDOWS_AUTH=true with Trusted_Connection."
        )
    base = (
        f"DRIVER={Config.SQL_DRIVER};"
        f"SERVER={Config.SQL_SERVER};"
        f"DATABASE={Config.SQL_DATABASE};"
        f"Encrypt={Config.SQL_ENCRYPT};"
        f"TrustServerCertificate={Config.SQL_TRUST_SERVER_CERTIFICATE};"
        "Connection Timeout=30;"
    )
    if Config.SQL_USE_WINDOWS_AUTH:
        conn_str = base + "Trusted_Connection=yes;"
    else:
        conn_str = (
            base
            + f"UID={Config.SQL_USERNAME};"
            + f"PWD={Config.SQL_PASSWORD};"
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
