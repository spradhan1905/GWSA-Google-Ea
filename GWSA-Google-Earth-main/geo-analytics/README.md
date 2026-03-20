# 🌍 GWSA GeoAnalytics

**Goodwill Industries of San Antonio** — Interactive Geospatial Analytics Platform

A full-stack internal web application that displays an interactive satellite map of all GWSA / Texas Thrift store locations, donation stations, and drop boxes across San Antonio and South Texas. Click any location pin to see a live financial/operational dashboard, powered by SQL Server data and a Gemini AI assistant.

---

## 🚀 Quick Start

### Prerequisites
- **Node.js** 18+ and npm
- **Python** 3.10+ and pip
- **SQL Server** (optional — demo mode works without it)

### Backend Setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env         # Fill in real values
python app.py                  # http://localhost:5000
```

### Frontend Setup
```bash
cd frontend
npm install
# Edit .env.local with your Google Maps API key
npm run dev                    # http://localhost:5173
```

---

## 🔑 API Keys Required

| Key | Where to Get It | File |
|-----|----------------|------|
| `VITE_GOOGLE_MAPS_API_KEY` | [Google Cloud Console](https://console.cloud.google.com) → Maps JS API | `frontend/.env.local` |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) | `backend/.env` |
| SQL Server credentials | GWSA IT / Azure Portal | `backend/.env` |

---

## 🏗️ Architecture

```
frontend/ (React + Vite + Tailwind)    →  backend/ (Python Flask)    →  SQL Server
                                           ↓
                                      Google Gemini API
```

## 📦 Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Tailwind CSS v3 |
| Maps | Google Maps JavaScript API (Satellite/Hybrid) |
| Charts | Recharts |
| Backend | Python Flask, Flask-CORS, Flask-Limiter |
| Database | SQL Server (pyodbc) |
| AI | Google Gemini 1.5 Flash |
| Security | Flask-Talisman, DOMPurify, marshmallow |

## 🔒 Security

- Rate limiting on all endpoints (Flask-Limiter)
- Parameterized SQL queries only (no string concatenation)
- Server-side input validation (marshmallow schemas)
- XSS prevention (DOMPurify on AI responses)
- API keys never exposed to browser
- Read-only SQL user (`gwsa_app_user`)
- CSP, HSTS, X-Frame-Options (Flask-Talisman)

## Pre-Deploy Security Checklist
- [ ] pip-audit — 0 high/critical findings
- [ ] npm audit — 0 high/critical findings
- [ ] .env is NOT committed (check: git status)
- [ ] FLASK_DEBUG=False in production .env
- [ ] force_https=True in Talisman (production only)
- [ ] CORS_ORIGIN set to production domain (not localhost)
- [ ] Google Maps API key restricted to prod domain in GCP Console
- [ ] SQL user is read-only gwsa_app_user (not admin)
- [ ] Rate limit test: 15 rapid /api/chat calls → should get 429

---

*Built for Goodwill Industries of San Antonio · Stack: React + Flask + Google Maps + Gemini AI + SQL Server*
