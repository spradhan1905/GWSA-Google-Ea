"""
GWSA GeoAnalytics — Authentication helpers
Reads the caller identity that Azure App Service Easy Auth injects.

When Easy Auth is enabled on the Web App with "Require authentication",
every request that reaches Flask has already been validated by Azure and
these headers are present:
  - X-MS-CLIENT-PRINCIPAL-ID    → Entra object id (stable user id)
  - X-MS-CLIENT-PRINCIPAL-NAME  → user principal name (email-ish)
  - X-MS-CLIENT-PRINCIPAL-IDP   → identity provider (e.g. 'aad')
  - X-MS-CLIENT-PRINCIPAL       → base64(JSON) with full claims

Locally (Flask dev server with no Easy Auth in front) the headers will be
missing; we return None so local dev still works without auth.
"""
import base64
import json
import functools
from flask import request, jsonify, g


def get_current_user():
    """Return {id, name, idp, claims} for the caller, or None if unauthenticated."""
    principal_id = request.headers.get('X-MS-CLIENT-PRINCIPAL-ID')
    principal_name = request.headers.get('X-MS-CLIENT-PRINCIPAL-NAME')

    if not principal_id and not principal_name:
        return None

    claims = {}
    raw = request.headers.get('X-MS-CLIENT-PRINCIPAL')
    if raw:
        try:
            decoded = base64.b64decode(raw).decode('utf-8')
            claims = json.loads(decoded)
        except (ValueError, json.JSONDecodeError):
            claims = {}

    return {
        'id': principal_id,
        'name': principal_name,
        'idp': request.headers.get('X-MS-CLIENT-PRINCIPAL-IDP', 'aad'),
        'claims': claims,
    }


def require_user(view):
    """Optional decorator: reject requests that arrive without Easy Auth headers.
    Useful in production as a belt-and-suspenders check. In local dev, setting
    AUTH_DISABLED=true skips the check."""
    import os

    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if os.environ.get('AUTH_DISABLED', '').lower() == 'true':
            g.current_user = None
            return view(*args, **kwargs)

        user = get_current_user()
        if not user:
            return jsonify(error='Unauthorized'), 401

        g.current_user = user
        return view(*args, **kwargs)

    return wrapper
