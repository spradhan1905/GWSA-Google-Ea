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

Optional — census tract income layer (backend only, never frontend):
- `CENSUS_API_KEY=your_census_gov_api_key` — only needed to **rebuild** `backend/data/census/texas_tracts_acs.geojson` on the server (or build locally and deploy the files). The running app serves pre-built GeoJSON and does not call Census on each map load.
- Deploy `backend/data/census/texas_tracts_acs.geojson` and `texas_tracts_acs.meta.json` with the backend, or run `python scripts/build_texas_census_tract_layer.py` once on App Service (SSH/Kudu) with `CENSUS_API_KEY` set.
- Confirm: `GET /api/health` → `texas_tract_income_layer_built: true`

Do **not** add `CENSUS_API_KEY` to Static Web Apps / `VITE_*` variables — that would expose the key in the browser.

## Validation

After deployment:
- Open `https://YOUR-BACKEND.azurewebsites.net/api/health`
- Confirm the frontend can load locations from the backend.
- Ask the AI assistant a simple non-sensitive question.
- Check App Service logs for SQL driver or connection errors.
