"""
Prepare Berlin district boundaries for the dashboard.

Keeps the required district fields, converts the geometry to EPSG:4326,
checks that all 12 districts are present, and saves the processed GeoJSON.
"""

from pathlib import Path

import geopandas as gpd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "boundaries"
    / "berlin_bezirke.json"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "berlin_bezirke.geojson"
)


# Load district boundaries
districts = gpd.read_file(RAW_PATH)


# Keep the fields used later in the project
districts = districts[
    [
        "name",
        "gem",
        "namgem",
        "geometry",
    ]
].rename(
    columns={
        "name": "district_id",
        "gem": "district_code",
        "namgem": "district_name",
    }
)


# Convert from EPSG:25833 to latitude/longitude coordinates
districts = districts.to_crs("EPSG:4326")


# Basic checks before saving
assert len(districts) == 12, "Expected 12 Berlin districts."

assert districts["district_name"].notna().all(), (
    "Some district names are missing."
)


# Save processed boundaries
OUTPUT_PATH.parent.mkdir(
    parents=True,
    exist_ok=True,
)

districts.to_file(
    OUTPUT_PATH,
    driver="GeoJSON",
)


print("=" * 60)
print("BERLIN DISTRICTS PREPARED")
print("=" * 60)

print("Rows:", len(districts))
print("CRS:", districts.crs)

print("\nDistricts:")
print(
    districts[
        ["district_code", "district_name"]
    ]
    .sort_values("district_code")
    .to_string(index=False)
)

print("\nSaved to:")
print(OUTPUT_PATH)