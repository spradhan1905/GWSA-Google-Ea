# Texas median income map layer

Area-level **median household income** for the whole state of Texas, with hover details per **census tract** (not city-wide averages).

## Data source (official, free)

| Piece | Source |
|-------|--------|
| Income & demographics | [U.S. Census ACS 5-Year](https://www.census.gov/programs-surveys/acs) via [Census Data API](https://www.census.gov/data/developers/data-assets.html) |
| Boundaries | [Cartographic tract file](https://www.census.gov/geographies/mapping-files/2024/geo/carto-boundary-file.html) (`cb_2024_48_tract_20m`) |

**Geography:** Census tracts (~1,200–8,000 people each). Texas has ~6,900 tracts. This is the finest practical ACS layer for a statewide hover map.

**Not included:** ZIP codes (ZCTAs), block groups, or city limits — tracts are the standard “neighborhood-scale” unit.

## Metrics on hover

- Median household income (`B19013_001E`)
- Margin of error (`B19013_001M`)
- Population (`B01003_001E`)
- Households (`B19001_001E`)
- Poverty rate (derived from `B17001`)
- Median home value (`B25077_001E`)
- Occupied housing units (`B25003_001E`)

## One-time setup

1. **Census API key** (free): https://api.census.gov/data/key_signup.html  

2. Add to `backend/.env`:

   ```env
   CENSUS_API_KEY=your_key_here
   ```

3. Install deps and build (from `geo-analytics/backend`):

   ```bash
   pip install -r requirements.txt
   python scripts/build_texas_census_tract_layer.py
   ```

   The script pulls ACS for all 254 counties (~2–5 minutes), then tract boundaries. If Census FTP returns **520/timeout** (common on corporate networks), it automatically falls back to **Census TIGERweb** (no extra install).

   Output files:

   - `data/census/texas_tracts_acs.geojson` (full Texas)
   - `data/census/texas_tracts_acs_metro.geojson` (San Antonio metro counties — used on mobile)
   - `data/census/texas_tracts_acs.meta.json` (legend breaks, vintage)

4. Restart the Flask API.

## Using the map

1. Open the app map view.
2. Click the **layers** control (stack icon) on the right toolbar.
3. **Desktop:** hover a tract for income and related metrics.
4. **Mobile:** tap a tract (loads San Antonio metro area only — avoids Safari memory crashes from the full-state file).
5. Zoom out to see statewide patterns on desktop; mobile is limited to the metro layer.

## API (for other clients)

| Endpoint | Description |
|----------|-------------|
| `GET /api/census/texas-tract-income/meta?scope=full\|metro` | Vintage, metric list, legend breaks |
| `GET /api/census/texas-tract-income?scope=full\|metro` | GeoJSON `FeatureCollection` (gzip when supported) |

**Mobile apps should use `scope=metro`.** Full Texas is ~100+ MB JSON and will crash mobile Safari.

## Refreshing data

Re-run the build script when a new ACS 5-year release ships (typically each December). Update `ACS_VINTAGE` in `backend/census/acs_variables.py` if needed.

## Production notes

- Full-state GeoJSON is very large (~100+ MB). Build in CI and deploy both full and metro files with the backend.
- GitHub Actions must run `build_texas_census_tract_layer.py` (see `AZURE_DEPLOYMENT.md`).

## License

U.S. Census Bureau data is public domain. Attribute Census/ACS in user-facing copy if required by your policy.
