"""
Inspect selected fields from the raw mobility datasets in more detail.

Looks at cycling station metadata and worksheet structure, roadwork fields,
and a sample of Berlin stops from the VBB GTFS feed.
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"


# Berlin district names
print("\n" + "=" * 60)
print("BERLIN DISTRICT NAMES")
print("=" * 60)

districts = gpd.read_file(
    RAW_DIR / "boundaries" / "berlin_bezirke.json"
)

print(
    districts[
        ["name", "gem", "namgem"]
    ].to_string(index=False)
)


# Cycling station metadata
cycling_path = (
    RAW_DIR
    / "cycling"
    / "gesamtdatei-stundenwerte.xlsx"
)

print("\n" + "=" * 60)
print("CYCLING — STANDORTDATEN")
print("=" * 60)

# Read the physical worksheet rows first before deciding which row is the header.
station_raw = pd.read_excel(
    cycling_path,
    sheet_name="Standortdaten",
    header=None,
    nrows=20,
)

print(station_raw.to_string())


# Cycling annual worksheet structure
print("\n" + "=" * 60)
print("CYCLING — 2025 RAW STRUCTURE")
print("=" * 60)

cycling_2025_raw = pd.read_excel(
    cycling_path,
    sheet_name="Jahresdatei 2025",
    header=None,
    nrows=20,
)

print(cycling_2025_raw.to_string())


# Roadworks fields
print("\n" + "=" * 60)
print("ROADWORKS DETAILS")
print("=" * 60)

roadworks = gpd.read_file(
    RAW_DIR
    / "roadworks"
    / "baustellen_sperrungen_viz.json"
)

columns_to_show = [
    "id",
    "subtype",
    "severity",
    "street",
    "section",
    "total_lanes",
    "closed_lanes",
    "validity",
    "is_future",
]

print(
    roadworks[
        columns_to_show
    ].head(10).to_string()
)

print("\nSubtype values:")
print(roadworks["subtype"].value_counts(dropna=False))

print("\nSeverity values:")
print(roadworks["severity"].value_counts(dropna=False))

print("\nGeometry types:")
print(roadworks.geometry.geom_type.value_counts())


# GTFS stop sample for Berlin
print("\n" + "=" * 60)
print("GTFS — BERLIN STOP SAMPLE")
print("=" * 60)

import zipfile

gtfs_path = RAW_DIR / "gtfs" / "GTFS.zip"

with zipfile.ZipFile(gtfs_path) as gtfs_zip:

    stops = pd.read_csv(
        gtfs_zip.open("stops.txt"),
        low_memory=False,
    )

print("Total VBB stops:", len(stops))

# VBB stop IDs containing de:11000 are useful for an initial Berlin check.
berlin_id_sample = stops[
    stops["stop_id"]
    .astype(str)
    .str.contains("de:11000:", na=False)
]

print(
    "Stops with Berlin code:",
    len(berlin_id_sample)
)

print(
    berlin_id_sample[
        ["stop_id", "stop_name", "stop_lat", "stop_lon"]
    ]
    .head(20)
    .to_string(index=False)
)