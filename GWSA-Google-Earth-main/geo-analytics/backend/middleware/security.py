"""
GWSA GeoAnalytics — Security Middleware
Rate limiting, input validation schemas, SQL safety checks.
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from marshmallow import Schema, fields, validate, ValidationError
import re
import functools
from flask import request, jsonify

# ─── Rate Limiter ───────────────────────────────────────────
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per hour", "50 per minute"],
    storage_uri="memory://"  # Upgrade to redis:// in production
)

# ─── Validation Schemas ────────────────────────────────────
class FinancialsQuerySchema(Schema):
    start = fields.Date(required=True)
    end   = fields.Date(required=True)
    # When true, daily Core revenue comes from TotalCoreTableFinal for the requested start/end (This Month or custom range in UI).
    this_month = fields.Bool(load_default=False)

class DoorCountQuerySchema(Schema):
    start = fields.Date(required=True)
    end   = fields.Date(required=True)

class TrendsQuerySchema(Schema):
    months = fields.Int(load_default=12, validate=validate.Range(min=1, max=60))

class ChatRequestSchema(Schema):
    message              = fields.Str(required=True, validate=validate.Length(min=1, max=2000))
    store_context        = fields.Str(load_default=None, validate=validate.Length(max=50))
    conversation_history = fields.List(fields.Dict(), load_default=[], validate=validate.Length(max=20))

# ─── Store ID Validation ───────────────────────────────────
def validate_store_id(store_id: str) -> bool:
    """Alphanumeric + underscores + hyphens only. Blocks path traversal."""
    return bool(re.match(r'^[a-zA-Z0-9_\- ]{1,80}$', store_id))

def require_valid_store(f):
    """Decorator: validate store_id path param before it reaches the DB."""
    @functools.wraps(f)
    def wrapper(store_id, *args, **kwargs):
        if not validate_store_id(store_id):
            return jsonify(error="Invalid store ID"), 400
        return f(store_id, *args, **kwargs)
    return wrapper

# ─── SQL Safety Gate ───────────────────────────────────────
FORBIDDEN_SQL_KEYWORDS = [
    'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'EXEC',
    'EXECUTE', 'TRUNCATE', 'CREATE', 'GRANT', 'REVOKE',
    'MERGE', 'BULK', 'OPENROWSET', 'xp_'
]

def is_safe_sql(sql: str) -> bool:
    """Safety gate on any AI-generated SQL before execution."""
    sql_upper = sql.upper()
    return not any(kw in sql_upper for kw in FORBIDDEN_SQL_KEYWORDS)
