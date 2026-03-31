# GWSA GeoAnalytics — Cursor Project Spec (v2)
> **Vibe-coded build guide for Cursor AI**
> Organization: Goodwill Industries of San Antonio (GWSA)
> Project codename: `geo-analytics`
> Last updated: 2026-02-27

---

## 🧭 What We're Building

A full-stack internal web application that displays an interactive satellite map of all GWSA / Texas Thrift store locations, donation stations, and drop boxes across San Antonio and South Texas. Users click any location pin and see a live financial/operational dashboard panel for that location — powered by SQL Server data. A Gemini AI chat assistant is embedded in the app so users can ask questions in plain English.

---

## 🗂️ Project Structure

```
geo-analytics/
├── frontend/                  # React + Vite SPA
│   ├── src/
│   │   ├── components/
│   │   │   ├── Map/
│   │   │   │   ├── MapContainer.jsx       # Google Maps embed wrapper
│   │   │   │   ├── LocationPin.jsx        # Custom pin component per type
│   │   │   │   └── KmlOverlay.jsx         # Renders KML layer on map
│   │   │   ├── Panel/
│   │   │   │   ├── SidePanel.jsx          # Slide-in panel on pin click
│   │   │   │   ├── MetricCard.jsx         # Single KPI card
│   │   │   │   ├── TrendChart.jsx         # Recharts line/bar chart
│   │   │   │   ├── MetricSelector.jsx     # Toggle: Financials / Door Count / Trends
│   │   │   │   └── DateRangePicker.jsx    # Period selector
│   │   │   ├── Chat/
│   │   │   │   ├── ChatDrawer.jsx         # Slide-up Gemini chat UI
│   │   │   │   ├── ChatMessage.jsx        # Individual message bubble
│   │   │   │   └── ChatInput.jsx          # Input bar + send button
│   │   │   └── Layout/
│   │   │       ├── TopBar.jsx             # App header + store search
│   │   │       └── LoadingSpinner.jsx
│   │   ├── hooks/
│   │   │   ├── useLocationData.js
│   │   │   ├── useGeminiChat.js
│   │   │   └── useKmlData.js
│   │   ├── services/
│   │   │   ├── api.js                     # Axios base + all backend calls
│   │   │   └── gemini.js                  # Proxy-only — no API key in browser
│   │   ├── data/
│   │   │   └── stores.js                  # Parsed KML store list (static seed)
│   │   ├── utils/
│   │   │   ├── kmlParser.js
│   │   │   ├── sanitize.js                # DOMPurify wrapper — XSS prevention
│   │   │   └── formatters.js
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── public/
│   │   └── gwsa-geo.kml
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
│
├── backend/                   # Python Flask API
│   ├── app.py                 # Flask app factory + security middleware
│   ├── routes/
│   │   ├── locations.py
│   │   ├── financials.py
│   │   ├── door_count.py
│   │   └── chat.py            # POST /api/chat — Gemini proxy
│   ├── db/
│   │   ├── connection.py      # SQL Server connection (pyodbc)
│   │   └── queries.py         # Parameterized queries ONLY — never string concat
│   ├── middleware/
│   │   └── security.py        # Rate limiter, input schemas, SQL safety check
│   ├── models/
│   │   └── schema.sql
│   ├── config.py
│   ├── requirements.txt
│   ├── .env.example
│   └── .gitignore             # .env MUST be listed here
│
└── README.md
```

---

## ⚙️ Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Frontend | React 18 + Vite | Fast HMR dev experience |
| Map | Google Maps JavaScript API v3 | Satellite view, KML overlay |
| Charts | Recharts | Line, bar, area charts |
| Styling | Tailwind CSS v3 | Dark theme, utility-first |
| HTTP Client | Axios | Frontend → Backend |
| Backend | Python Flask + Flask-CORS | REST API |
| Rate Limiting | Flask-Limiter | Per-IP + per-endpoint throttles |
| Security Headers | Flask-Talisman | CSP, HSTS, X-Frame-Options, nosniff |
| Input Validation | marshmallow | Schema-based server-side validation |
| Database | SQL Server via `pyodbc` | Parameterized queries only |
| AI | Google Gemini `gemini-1.5-flash` | Server-side proxy only |
| XSS Sanitizer | DOMPurify | Sanitize AI responses before rendering |
| Icons | Lucide React | |
| Date Picker | React DatePicker | |
              
---

## 🔒 SECURITY HARDENING (Full Implementation)

> Based on the pre-launch security checklist:
> Rate Limits → Row Level Security → Server-side validation → API keys secured
> → Env vars set properly → CORS restrictions → Dependency audit

---

### 1. ✅ Rate Limits — `middleware/security.py`

Prevent abuse, DoS attempts, and Gemini API cost blowout.

```python
# backend/middleware/security.py
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per hour", "50 per minute"],
    storage_uri="memory://"   # Upgrade to "redis://localhost:6379" in production
)

# Per-endpoint limits applied as decorators in each route file:
# @limiter.limit("10 per minute")   → /api/chat      (Gemini costs money)
# @limiter.limit("30 per minute")   → /api/financials
# @limiter.limit("30 per minute")   → /api/door-count
# @limiter.limit("60 per minute")   → /api/locations
```

```python
# backend/app.py — register limiter + clean JSON error on 429
from middleware.security import limiter
limiter.init_app(app)

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify(error="Too many requests. Please slow down."), 429
```

---

### 2. ✅ Row Level Security — SQL Server

Enforced at two levels — application AND database.

**Level 1 — Application: Always scope queries by `LocationID`**

```python
# db/queries.py — ALWAYS parameterize, NEVER concatenate
def get_financials(store_id: str, start_date: str, end_date: str):
    sql = """
        SELECT PeriodMonth, NetRevenue, NetIncome, ExpenseRatio,
               DonatedGoodsRev, RetailRevenue
        FROM dbo.Financials
        WHERE LocationID = ?          -- parameterized
          AND PeriodMonth BETWEEN ? AND ?
        ORDER BY PeriodMonth
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, (store_id, start_date, end_date))
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]
```

**Level 2 — SQL Server: Dedicated read-only app user**

```sql
-- Run once as SA/admin in SQL Server Management Studio
CREATE LOGIN gwsa_app_user WITH PASSWORD = 'StrongPasswordHere!';
CREATE USER  gwsa_app_user FOR LOGIN gwsa_app_user;

GRANT SELECT ON dbo.Locations      TO gwsa_app_user;
GRANT SELECT ON dbo.Financials     TO gwsa_app_user;
GRANT SELECT ON dbo.DoorCount      TO gwsa_app_user;
GRANT SELECT ON dbo.DonorAddresses TO gwsa_app_user;

-- Even if the app is compromised, attacker cannot modify data
DENY INSERT, UPDATE, DELETE, DROP, ALTER ON dbo.Financials TO gwsa_app_user;
```

Use `gwsa_app_user` in `.env` — not an admin account.

---

### 3. ✅ Server-Side Validation — marshmallow schemas

Never trust the frontend. Every request is validated on the server before touching the DB.

```python
# middleware/security.py
from marshmallow import Schema, fields, validate, ValidationError
import re, functools
from flask import request, jsonify

class FinancialsQuerySchema(Schema):
    start = fields.Date(required=True)
    end   = fields.Date(required=True)

class ChatRequestSchema(Schema):
    message              = fields.Str(required=True,
                                      validate=validate.Length(min=1, max=2000))
    store_context        = fields.Str(load_default=None,
                                      validate=validate.Length(max=50))
    conversation_history = fields.List(fields.Dict(), load_default=[],
                                       validate=validate.Length(max=20))

def validate_store_id(store_id: str) -> bool:
    """Alphanumeric + underscores + hyphens only. Blocks path traversal."""
    return bool(re.match(r'^[a-zA-Z0-9_-]{1,50}$', store_id))

def require_valid_store(f):
    """Decorator: validate store_id path param before it reaches the DB."""
    @functools.wraps(f)
    def wrapper(store_id, *args, **kwargs):
        if not validate_store_id(store_id):
            return jsonify(error="Invalid store ID"), 400
        return f(store_id, *args, **kwargs)
    return wrapper

FORBIDDEN_SQL_KEYWORDS = [
    'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'EXEC',
    'EXECUTE', 'TRUNCATE', 'CREATE', 'GRANT', 'REVOKE',
    'MERGE', 'BULK', 'OPENROWSET', 'xp_'
]

def is_safe_sql(sql: str) -> bool:
    """Safety gate on any AI-generated SQL before execution."""
    sql_upper = sql.upper()
    return not any(kw in sql_upper for kw in FORBIDDEN_SQL_KEYWORDS)
```

Apply in routes:

```python
# routes/financials.py
@financials_bp.route('/api/financials/<store_id>', methods=['GET'])
@limiter.limit("30 per minute")
@require_valid_store
def get_financials(store_id):
    schema = FinancialsQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as err:
        return jsonify(error=err.messages), 400
    data = queries.get_financials(store_id, params['start'], params['end'])
    return jsonify(data)
```

---

### 4. ✅ API Keys Secured — Never in the browser

```
❌ WRONG:  GEMINI_API_KEY in frontend .env → ships in JS bundle → anyone can read it
✅ RIGHT:  GEMINI_API_KEY only in backend/.env → Flask proxies all Gemini calls
```

```javascript
// frontend/services/gemini.js — thin wrapper, no key here
import api from './api';

export const sendChatMessage = (message, storeContext, history) =>
  api.post('/api/chat', {
    message,
    store_context: storeContext,
    conversation_history: history
  });
```

```bash
# frontend/.env.local — ONLY the Maps key goes here (safe — restricted in GCP)
VITE_GOOGLE_MAPS_API_KEY=your_maps_key_here
# ⚠️ NEVER add GEMINI_API_KEY here. NEVER add SQL credentials here.
```

**Restrict the Google Maps key in Google Cloud Console:**
- Application restriction: HTTP referrers → your domain only
- API restriction: Maps JavaScript API only
- This way even if someone sees the key, it won't work on their domain

---

### 5. ✅ Env Vars Set Properly

**`.gitignore` — Cursor must create this in both directories:**

```gitignore
# backend/.gitignore
.env
*.env
venv/
__pycache__/
*.pyc

# frontend/.gitignore
.env.local
.env.production
node_modules/
dist/
```

**`config.py` — fails fast on startup if any required var is missing:**

```python
# backend/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SQL_SERVER     = os.environ['SQL_SERVER']       # Raises KeyError if missing
    SQL_DATABASE   = os.environ['SQL_DATABASE']
    SQL_USERNAME   = os.environ['SQL_USERNAME']
    SQL_PASSWORD   = os.environ['SQL_PASSWORD']
    SQL_DRIVER     = os.environ.get('SQL_DRIVER', '{ODBC Driver 17 for SQL Server}')
    GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
    SECRET_KEY     = os.environ['FLASK_SECRET_KEY']
    CORS_ORIGIN    = os.environ.get('CORS_ORIGIN', 'http://localhost:5173')
    DEBUG          = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
```

**`.env.example` (safe to commit — no real values):**

```bash
# backend/.env.example — commit this file, NOT .env

SQL_SERVER=your-server.database.windows.net
SQL_DATABASE=GWSA_Analytics
SQL_USERNAME=gwsa_app_user
SQL_PASSWORD=REPLACE_WITH_REAL_PASSWORD
SQL_DRIVER={ODBC Driver 17 for SQL Server}

GEMINI_API_KEY=REPLACE_WITH_REAL_KEY
FLASK_SECRET_KEY=REPLACE_WITH_32_CHAR_RANDOM_STRING
FLASK_DEBUG=False

# Update to production domain before deploying
CORS_ORIGIN=http://localhost:5173
```

---

### 6. ✅ CORS Restrictions — explicit whitelist, never wildcard

```python
# backend/app.py
from flask_cors import CORS
from config import Config

# CORRECT: explicit origin whitelist
CORS(app,
     origins=[Config.CORS_ORIGIN],     # "http://localhost:5173" dev / prod domain
     methods=['GET', 'POST'],
     allow_headers=['Content-Type'],
     supports_credentials=False,
     max_age=3600
)

# For production, set in .env:
# CORS_ORIGIN=https://geo.goodwillsa.org
```

---

### 7. ✅ Security Headers — Flask-Talisman

One line adds 5 protective headers to every response.

```python
# backend/app.py
from flask_talisman import Talisman

csp = {
    'default-src': "'self'",
    'script-src':  ["'self'", "https://maps.googleapis.com", "https://maps.gstatic.com"],
    'style-src':   ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
    'img-src':     ["'self'", "data:", "https://*.googleapis.com", "https://*.gstatic.com"],
    'connect-src': ["'self'"],
    'frame-src':   "'none'",
}

Talisman(
    app,
    force_https=False,              # Set True in production
    strict_transport_security=True,
    content_security_policy=csp,
    referrer_policy='strict-origin-when-cross-origin',
)

# Headers automatically added to every response:
# X-Content-Type-Options: nosniff
# X-Frame-Options: SAMEORIGIN
# X-XSS-Protection: 1; mode=block
# Strict-Transport-Security: max-age=31536000
# Content-Security-Policy: ...
```

---

### 8. ✅ XSS Prevention — DOMPurify on AI output

React escapes content by default, but Gemini responses could contain HTML.

```javascript
// frontend/utils/sanitize.js
import DOMPurify from 'dompurify';

export const sanitizeHtml = (dirty) =>
  DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'br', 'p', 'ul', 'li'],
    ALLOWED_ATTR: []
  });
```

```javascript
// components/Chat/ChatMessage.jsx
import { sanitizeHtml } from '../../utils/sanitize';

const ChatMessage = ({ message, isAI }) => (
  <div className={`message ${isAI ? 'ai' : 'user'}`}>
    {isAI
      ? <div dangerouslySetInnerHTML={{ __html: sanitizeHtml(message) }} />
      : <p>{message}</p>   // User input: NEVER render as HTML
    }
  </div>
);
```

---

### 9. ✅ SQL Injection Prevention — Parameterized queries everywhere

```python
# db/queries.py

# ❌ NEVER — string interpolation = SQL injection vulnerability
def bad_query(store_id):
    sql = f"SELECT * FROM Financials WHERE LocationID = '{store_id}'"

# ✅ ALWAYS — ? placeholder, parameters passed separately
def get_door_count(store_id: str, start: str, end: str) -> list:
    sql = """
        SELECT CountDate, DonorVisits
        FROM dbo.DoorCount
        WHERE LocationID = ?
          AND CountDate BETWEEN ? AND ?
        ORDER BY CountDate
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, (store_id, start, end))
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]
```

For text-to-SQL: the `is_safe_sql()` function from `middleware/security.py` blocks
any AI-generated query containing write/destroy keywords before it executes.

---

### 10. ✅ Dependency Audit — Run before every deploy

```bash
# Backend
pip install pip-audit
pip-audit                   # Scan for CVEs
pip list --outdated         # See what's behind

# Frontend
npm audit                   # Scan for vulnerabilities
npm audit fix               # Auto-fix safe updates
npm outdated                # See what's behind
```

**Add to README as a pre-deploy gate:**

```markdown
## Pre-Deploy Security Checklist
- [ ] pip-audit — 0 high/critical findings
- [ ] npm audit  — 0 high/critical findings
- [ ] .env is NOT committed (check: git status)
- [ ] FLASK_DEBUG=False in production .env
- [ ] force_https=True in Talisman (production only)
- [ ] CORS_ORIGIN set to production domain (not localhost)
- [ ] Google Maps API key restricted to prod domain in GCP Console
- [ ] SQL user is read-only gwsa_app_user (not admin)
- [ ] Rate limit test: 15 rapid /api/chat calls → should get 429
```

---

## 🗺️ Map Requirements

### Google Maps Setup

```javascript
// vite.config.js — proxy API calls to Flask
export default defineConfig({
  server: {
    proxy: { '/api': 'http://localhost:5000' }
  }
})
```

```html
<!-- index.html — Maps key is safe here (restricted to this domain in GCP) -->
<script async
  src="https://maps.googleapis.com/maps/api/js?key=YOUR_GOOGLE_MAPS_API_KEY&libraries=places&callback=initMap">
</script>
```

### Map Initialization (MapContainer.jsx)

```javascript
const MAP_CENTER = { lat: 29.4999, lng: -98.5018 };   // San Antonio, TX
const MAP_ZOOM = 11;

const mapOptions = {
  mapTypeId: 'hybrid',           // Satellite + labels (Google Earth feel)
  tilt: 0,
  mapTypeControl: true,
  streetViewControl: false,
  fullscreenControl: true,
};
```

### KML Overlay

The KML file (`gwsa-geo.kml`) contains 3,066 placemarks:

- **Border** — 8 line segments defining the SA service territory
- **Stores** — Named retail locations organized by store manager
- **ADC Locations** — Attended Donation Centers
- **Drop Boxes** — 40 Texas Thrift drop box locations
- **Donor Addresses** — 2,956 geocoded donor addresses (12 sub-layers)
- **Possible Expansion Locations** — Scouted potential new sites

```javascript
const kmlLayer = new google.maps.KmlLayer({
  url: `${window.location.origin}/gwsa-geo.kml`,
  map: map,
  suppressInfoWindows: true,
  preserveViewport: false
});

kmlLayer.addListener('click', (event) => {
  handlePinClick(event.featureData.name, event.latLng);
});
```

### Pin Click Behavior

- **Named store / ADC** → Side panel slides in with financial dashboard
- **Donor address pin** → Simple address tooltip only
- **Drop box pin** → Tooltip + "View nearest store" button

---

## 📊 Side Panel

Width: `420px`. Slides in from the right. Dark background.

### Panel Header
```
[ ← Back ]   [Store Name]   [Store Type Badge]
             Store Manager: [Name]
             Last Updated: [timestamp]
```

### Metric Selector Tabs
```
[ Financials ]  [ Door Count ]  [ Trends ]  [ Donor Map ]
```

### Tab 1: Financials

Period selector: `This Month | This Quarter | This Year | Custom`

KPI cards (2-column grid):

| Metric | Format |
|--------|--------|
| Net Revenue | `$XXX,XXX` |
| Net Income | `$XX,XXX` + ↑↓ vs prior period |
| Expense Ratio | `XX.X%` |
| Donated Goods Revenue | `$XX,XXX` |
| Retail Revenue | `$XX,XXX` |
| YTD Net Income | `$XX,XXX` |

Below cards: line chart of Net Income over selected period.

### Tab 2: Door Count
KPI cards + bar chart of daily counts.

### Tab 3: Trends
Multi-series line chart — user toggles: Net Income, Door Count, Expense Ratio, Donated Goods Volume.

### Tab 4: Donor Map
Mini Google Map showing KML donor pins for that store's catchment layer.

---

## 🔌 Backend API Endpoints

#### `GET /api/locations`
Returns full store list.

#### `GET /api/financials/<store_id>?start=2024-01-01&end=2024-12-31`
Returns summary KPIs + monthly breakdown.

#### `GET /api/door-count/<store_id>?start=2024-01-01&end=2024-12-31`
Returns total, daily average, peak day, daily array.

#### `GET /api/trends/<store_id>?months=12`
Returns multi-series trend data.

#### `POST /api/chat`
Gemini proxy. Accepts `message`, `store_context`, `conversation_history`.
Returns `reply`, `sql_used`, `data`.

---

## 🤖 Gemini AI Chat (routes/chat.py)

```python
import google.generativeai as genai
from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from middleware.security import limiter, ChatRequestSchema, is_safe_sql
from db.connection import get_connection
from config import Config

chat_bp = Blueprint('chat', __name__)
genai.configure(api_key=Config.GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

SYSTEM_CONTEXT = """
You are a data analyst assistant for Goodwill Industries of San Antonio (GWSA) and Texas Thrift.
You have access to store financial data, door counts, and location information across
San Antonio, South Texas, and Laredo. Be concise, professional, and data-driven.
Store types: retail stores, ADC (Attended Donation Centers), outlets, drop boxes.
Key managers: Rusty Alston, John Aguirre, Martha Medina, Marco Pompa.
"""

@chat_bp.route('/api/chat', methods=['POST'])
@limiter.limit("10 per minute")
def chat():
    schema = ChatRequestSchema()
    try:
        data = schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        return jsonify(error=err.messages), 400

    user_message  = data['message']
    store_context = data.get('store_context')
    history       = data.get('conversation_history', [])

    context = SYSTEM_CONTEXT
    if store_context:
        context += f"\nUser is viewing: '{store_context}' location."

    sql_result, sql_used = None, None
    data_kws = ['highest', 'lowest', 'compare', 'trend', 'revenue',
                'income', 'door count', 'best', 'worst', 'total']
    if any(kw in user_message.lower() for kw in data_kws):
        sql_used, sql_result = try_text_to_sql(user_message, store_context)

    full_prompt = context
    if sql_result:
        full_prompt += f"\n\nRelevant DB data:\n{sql_result}"
    full_prompt += f"\n\nUser question: {user_message}"

    response = model.generate_content(full_prompt)
    return jsonify({'reply': response.text, 'sql_used': sql_used, 'data': sql_result})


def try_text_to_sql(question: str, store_id: str):
    schema_hint = """
    Tables:
      Locations(LocationID, LocationName, LocationType, Manager)
      Financials(LocationID, PeriodMonth DATE, NetRevenue, NetIncome, ExpenseRatio,
                 DonatedGoodsRev, RetailRevenue)
      DoorCount(LocationID, CountDate DATE, DonorVisits INT)
    """
    sql_prompt = f"""
    Schema: {schema_hint}
    Write a single safe SQL Server SELECT query to answer: "{question}"
    Rules: SELECT only. TOP 100 max. No INSERT/UPDATE/DELETE/DROP/EXEC.
    Return ONLY the SQL — no markdown, no explanation.
    """
    try:
        sql_response = model.generate_content(sql_prompt)
        sql_query    = sql_response.text.strip().replace('```sql','').replace('```','').strip()

        if not is_safe_sql(sql_query):
            return None, None

        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql_query)
        cols   = [d[0] for d in cursor.description]
        result = [dict(zip(cols, row)) for row in cursor.fetchall()]
        return sql_query, result
    except Exception:
        return None, None
```

---

## 🗄️ SQL Server Schema (models/schema.sql)

```sql
-- ============================================
-- GWSA GeoAnalytics — SQL Server Schema
-- Goodwill Industries of San Antonio
-- ============================================

CREATE TABLE dbo.Locations (
    LocationID      VARCHAR(50)   PRIMARY KEY,
    LocationName    NVARCHAR(100) NOT NULL,
    LocationType    VARCHAR(20)   NOT NULL
        CONSTRAINT CK_LocationType CHECK (LocationType IN ('store','adc','outlet','dropbox')),
    Manager         NVARCHAR(100),
    Latitude        DECIMAL(9,6),
    Longitude       DECIMAL(9,6),
    IsActive        BIT           DEFAULT 1,
    CreatedAt       DATETIME      DEFAULT GETDATE()
);

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
```

---

## 🎨 UI Design

### Color Palette (Dark — Google Earth Inspired)

```css
:root {
  --bg-primary:   #1a1a2e;
  --bg-secondary: #16213e;
  --bg-card:      #0f3460;
  --accent:       #e94560;
  --accent-green: #00b4d8;
  --text-primary: #eaeaea;
  --text-muted:   #94a3b8;
  --border:       #2d3748;
  --success:      #10b981;
  --warning:      #f59e0b;
  --danger:       #ef4444;
}
```

### Layout

```
┌──────────────────────────────────────────────────────────┐
│  TopBar: GWSA Logo | Search Stores | [AI Chat Button]     │
├────────────────────────────┬─────────────────────────────┤
│                            │  SidePanel (slides in)       │
│   Google Maps satellite    │  ┌──────────────────────┐   │
│   centered on San Antonio  │  │ Store Name + Badge   │   │
│                            │  │ Manager name         │   │
│   [KML pins overlay]       │  ├──────────────────────┤   │
│                            │  │ [Fin][Door][Trend]   │   │
│                            │  ├──────────────────────┤   │
│                            │  │ KPI Cards (2-col)    │   │
│                            │  ├──────────────────────┤   │
│                            │  │ Trend Chart          │   │
│                            │  └──────────────────────┘   │
└────────────────────────────┴─────────────────────────────┘
                         [💬 Ask Gemini]  ← floating bottom-right
```

---

## 📦 Dependencies

### Frontend (package.json)

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "axios": "^1.6.0",
    "recharts": "^2.10.0",
    "lucide-react": "^0.263.1",
    "react-datepicker": "^6.2.0",
    "tailwindcss": "^3.4.0",
    "@tailwindcss/forms": "^0.5.7",
    "date-fns": "^3.0.0",
    "dompurify": "^3.1.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.0",
    "vite": "^5.0.0",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.31"
  }
}
```

### Backend (requirements.txt)

```
flask==3.0.0
flask-cors==4.0.0
flask-limiter==3.5.0
flask-talisman==1.1.0
marshmallow==3.20.0
pyodbc==5.0.1
python-dotenv==1.0.0
google-generativeai==0.7.0
pandas==2.1.4
pip-audit==2.7.0
```

---

## 🚀 Getting Started

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # Fill in real values
pip-audit                       # Check for vulnerabilities first
python app.py                   # http://localhost:5000
```

### Frontend

```bash
cd frontend
npm install
npm audit                       # Check for vulnerabilities
# Create frontend/.env.local:
# VITE_GOOGLE_MAPS_API_KEY=your_key_here
npm run dev                     # http://localhost:5173
```

---

## 🧱 Build Order for Cursor

1. **Flask skeleton** — `app.py`, `config.py`, CORS, Talisman, health check
2. **Rate limiter** — `middleware/security.py`, register Flask-Limiter, 429 handler
3. **DB connection** — `db/connection.py`, test query
4. **Validation schemas** — marshmallow in `middleware/security.py`
5. **Locations endpoint** — `/api/locations` with `require_valid_store`
6. **React + Vite setup** — base app, Tailwind, `sanitize.js` added immediately
7. **Google Maps component** — satellite map centered on San Antonio
8. **KML overlay** — load `gwsa-geo.kml`, suppress default info windows
9. **Pin click handler** — capture store name + coords
10. **Side Panel UI** — slide-in panel with tabs (mock data first)
11. **Financials API + charts** — `/api/financials` + Recharts
12. **Door Count API + charts** — `/api/door-count`
13. **Trends tab** — multi-series chart with toggles
14. **Gemini chat** — Flask proxy + React chat drawer + DOMPurify on AI output
15. **Text-to-SQL** — add to chat route with `is_safe_sql()` guard
16. **Dependency audit** — `pip-audit` + `npm audit`, fix high/critical findings
17. **Polish** — loading states, error states, 429 handling in frontend

---

## 🔑 API Keys Needed

| Key | Where to get it | Location | Notes |
|-----|----------------|----------|-------|
| `VITE_GOOGLE_MAPS_API_KEY` | Google Cloud Console → Maps JS API | `frontend/.env.local` | Restrict to your domain in GCP |
| `GEMINI_API_KEY` | aistudio.google.com | `backend/.env` only | Never in frontend |
| SQL Server credentials | GWSA IT / Azure portal | `backend/.env` only | Use `gwsa_app_user` (read-only) |

---

## 📝 Design Decisions

| Decision | Rationale |
|----------|-----------|
| KML as static file | Already geocoded — SQL is for financials only |
| Gemini via Flask proxy | API key never reaches the browser |
| No auth Phase 1 | Internal tool, fast to ship — Azure AD SSO in Phase 2 |
| Read-only SQL user `gwsa_app_user` | Compromised app can't modify data |
| marshmallow validation | Every request validated server-side before DB |
| Flask-Talisman | 5 security headers in one line |
| Flask-Limiter | Protects Gemini cost + DoS prevention |
| DOMPurify on AI output | Gemini responses could contain HTML/scripts |
| `is_safe_sql()` guard | Blocks write/destroy keywords in AI-generated SQL |
| Fails fast on missing env vars | Config error surfaces immediately at startup, not at runtime |

---

## 🔮 Phase 2 Ideas

- Azure AD SSO login
- Store manager territory heat map (donor density)
- Export panel data to Excel/PDF
- Alert system: flag stores where net income drops >10% MoM
- Redis-backed rate limiting (replace in-memory)
- Audit log: track which users viewed which store data

---

*Generated for Cursor AI — Goodwill Industries of San Antonio GeoAnalytics Project*
*Stack: React + Vite | Python Flask | Google Maps API | Gemini AI | SQL Server*
