# GWSA GeoAnalytics API — Linux image with Microsoft ODBC Driver for SQL Server (required by pyodbc).
# On Render: set Environment = Docker, Root Directory = geo-analytics/backend (or this folder),
# and set SQL_DRIVER={ODBC Driver 18 for SQL Server} (Driver 18 matches msodbcsql18 below).

FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PORT=5000

# Render injects PORT; gunicorn serves the module-level `app` in app.py
CMD exec gunicorn --bind "0.0.0.0:${PORT}" --workers 2 --threads 4 --timeout 120 app:app
