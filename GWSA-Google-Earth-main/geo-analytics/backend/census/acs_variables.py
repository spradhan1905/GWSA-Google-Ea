"""ACS 5-year variables used for Texas tract socioeconomic layer."""

ACS_VINTAGE = "2023"
ACS_DATASET = f"acs/acs5"

# state FIPS for Texas
TEXAS_STATE_FIPS = "48"

# Median income + related tract-level metrics (hover / detail panel)
ACS_GET_VARS = [
    "NAME",
    "B19013_001E",  # median household income
    "B19013_001M",  # income margin of error
    "B01003_001E",  # total population
    "B19001_001E",  # households (universe for income tab)
    "B17001_001E",  # poverty status universe
    "B17001_002E",  # below poverty level
    "B25077_001E",  # median home value
    "B25003_001E",  # occupied housing units
]

# Official TIGER/Line state tract ZIPs (see www2.census.gov/geo/tiger/TIGERYYYY/TRACT/)
TRACT_BOUNDARY_URLS = [
    "https://www2.census.gov/geo/tiger/TIGER2024/TRACT/tl_2024_48_tract.zip",
    "https://www2.census.gov/geo/tiger/TIGER2023/TRACT/tl_2023_48_tract.zip",
]
TRACT_BOUNDARY_URL = TRACT_BOUNDARY_URLS[0]
