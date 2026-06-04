# Azure Deployment

Recommended Azure resources:
- Frontend: Azure Static Web Apps
- Backend: Azure App Service for Linux, Python
- Database: Azure SQL or SQL Server reachable from the backend App Service

## Frontend

Azure Static Web Apps build settings:
- App location: `frontend`
- Build command: `npm run build`
- Output location: `dist`

Build-time environment variables:
- `VITE_API_BASE_URL=https://YOUR-BACKEND.azurewebsites.net`
- `VITE_GOOGLE_MAPS_API_KEY=REPLACE_WITH_GOOGLE_MAPS_BROWSER_KEY`

For Vite, these must be available during the frontend build, such as in the GitHub Actions workflow or Azure pipeline that builds Azure Static Web Apps. They are not backend App Service runtime settings.

Restrict the Google Maps key to the Azure Static Web Apps frontend domain.

## Backend

Azure App Service settings:
- Runtime stack: Python
- Deploy folder: `backend`
- Startup command: `sh startup.sh`

If Azure does not run the script directly, use this startup command:

```sh
sh startup.sh
```

Required environment variables:
- `FLASK_DEBUG=False`
- `FORCE_HTTPS=True`
- `FLASK_SECRET_KEY=REPLACE_WITH_32_CHAR_RANDOM_STRING`
- `CORS_ORIGINS=https://YOUR-FRONTEND.azurestaticapps.net`
- Azure OpenAI (set `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`)
- `SQL_SERVER=YOUR-SQL-HOST,1433`
- `SQL_DATABASE=JS_API`
- `SQL_DRIVER={ODBC Driver 18 for SQL Server}`
- `SQL_USE_WINDOWS_AUTH=False`
- `SQL_USERNAME=gwsa_app_user`
- `SQL_PASSWORD=REPLACE_WITH_REAL_PASSWORD`
- `SQL_ENCRYPT=yes`
- `SQL_TRUST_SERVER_CERTIFICATE=no`

Use `SQL_TRUST_SERVER_CERTIFICATE=yes` only when your SQL Server certificate is not trusted yet, such as during early testing.

### Census tract income layer (important)

The map calls `GET /api/census/texas-tract-income`. A **404 "Census layer not built"** means the GeoJSON files are missing on the server — **not** that the route is wrong.

The data files are **gitignored** and are **built during CI**, not read from Census at runtime.

1. **GitHub Actions secret (required for deploy)**  
   Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**  
   - Name: `CENSUS_API_KEY`  
   - Value: your key from https://api.census.gov/data/key_signup.html  

2. **Azure App Service `CENSUS_API_KEY` (optional)**  
   Only needed if you rebuild on the server via SSH/Kudu. The GitHub workflow builds the layer before deploy.

3. **Redeploy**  
   Push to `main` (or run workflow **Build and deploy Python app to Azure Web App - GWSA-backend** manually). The workflow runs `scripts/build_texas_census_tract_layer.py` (~3–8 min) and uploads `data/census/*.geojson` with the app.

4. **Verify**  
   - `https://YOUR-BACKEND.azurewebsites.net/api/health` → `"texas_tract_income_layer_built": true`  
   - `https://YOUR-BACKEND.azurewebsites.net/api/census/texas-tract-income/meta` → JSON (not 404)

Do **not** put `CENSUS_API_KEY` in Static Web Apps / `VITE_*` — that exposes the key in the browser.

## Validation

After deployment:
- Open `https://YOUR-BACKEND.azurewebsites.net/api/health`
- Confirm the frontend can load locations from the backend.
- Ask the AI assistant a simple non-sensitive question.
- Check App Service logs for SQL driver or connection errors.
