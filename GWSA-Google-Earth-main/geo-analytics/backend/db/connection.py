"""
GWSA GeoAnalytics — Database Connection
SQL Server via pyodbc with a small thread-safe connection pool.

Opening a fresh pyodbc connection per query is expensive (TCP + auth handshake to a
remote SQL Server, ~tens to hundreds of ms each). Chat ranking queries fan out across
every store, so that cost used to be paid dozens of times per request. The pool keeps a
handful of warm connections and hands them out / returns them instead of reconnecting.

pyodbc is imported lazily so the app can start before first DB access.
"""
import queue
import threading

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


def _connection_string() -> str:
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
        return base + "Trusted_Connection=yes;"
    return base + f"UID={Config.SQL_USERNAME};" + f"PWD={Config.SQL_PASSWORD};"


def get_connection():
    """Create a brand-new SQL Server connection (autocommit; we only run SELECTs)."""
    pyodbc = _get_pyodbc()
    conn = pyodbc.connect(_connection_string())
    # Read-only analytics: autocommit avoids holding an open transaction (and its locks /
    # snapshot) across the connection's pooled lifetime.
    try:
        conn.autocommit = True
    except Exception:
        pass
    return conn


class _ConnectionPool:
    """Minimal bounded, thread-safe pool of warm pyodbc connections."""

    def __init__(self, max_size: int):
        self._max_size = max(1, int(max_size))
        self._idle: "queue.LifoQueue" = queue.LifoQueue()
        self._lock = threading.Lock()
        self._open_count = 0
        self._semaphore = threading.Semaphore(self._max_size)

    def acquire(self, timeout: float):
        """Borrow a connection, blocking up to ``timeout`` seconds for a free slot."""
        if not self._semaphore.acquire(timeout=timeout):
            raise RuntimeError("Timed out waiting for a free database connection from the pool")
        try:
            try:
                return self._idle.get_nowait()
            except queue.Empty:
                pass
            conn = get_connection()
            with self._lock:
                self._open_count += 1
            return conn
        except Exception:
            # Failed to hand out a connection — release the slot we reserved.
            self._semaphore.release()
            raise

    def release(self, conn, broken: bool = False) -> None:
        """Return a connection to the pool, or discard it when broken."""
        if conn is None:
            return
        if broken:
            self._discard(conn)
        else:
            self._idle.put(conn)
        self._semaphore.release()

    def _discard(self, conn) -> None:
        try:
            conn.close()
        except Exception:
            pass
        with self._lock:
            self._open_count = max(0, self._open_count - 1)


_pool = None
_pool_lock = threading.Lock()


def _get_pool() -> _ConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = _ConnectionPool(Config.SQL_POOL_MAX_SIZE)
    return _pool


def acquire_pooled_connection():
    return _get_pool().acquire(timeout=Config.SQL_POOL_TIMEOUT_SEC)


def release_pooled_connection(conn, broken: bool = False) -> None:
    _get_pool().release(conn, broken=broken)


def test_connection() -> bool:
    """Quick health check for the database (uses a one-off connection, not the pool)."""
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
