"""
Inspect the raw files used by the Berlin Mobility Dashboard.

Prints basic structure and sample records for the district boundaries,
cycling workbook, roadworks data and VBB GTFS feed. No source files are modified.
"""

from pathlib import Path
import zipfile

import geopandas as gpd
import pandas as pd


# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"


# Berlin district boundaries
print("\n" + "=" * 60)
print("1. BERLIN DISTRICTS")
print("=" * 60)

district_path = RAW_DIR / "boundaries" / "berlin_bezirke.json"

districts = gpd.read_file(district_path)

print("Rows:", len(districts))
print("CRS:", districts.crs)
print("Columns:")
print(districts.columns.tolist())

print("\nFirst rows:")
print(districts.head())


# Cycling counters
print("\n" + "=" * 60)
print("2. CYCLING DATA")
print("=" * 60)

cycling_path = RAW_DIR / "cycling" / "gesamtdatei-stundenwerte.xlsx"

excel_file = pd.ExcelFile(cycling_path)

print("Excel sheets:")
print(excel_file.sheet_names)

# Read a small sample first.
cycling_sample = pd.read_excel(
    cycling_path,
    sheet_name=excel_file.sheet_names[0],
    nrows=10,
)

print("\nColumns:")
print(cycling_sample.columns.tolist())

print("\nSample:")
print(cycling_sample)


# Roadworks and disruptions
print("\n" + "=" * 60)
print("3. ROADWORKS")
print("=" * 60)

roadworks_path = RAW_DIR / "roadworks" / "baustellen_sperrungen_viz.json"

roadworks = gpd.read_file(roadworks_path)

print("Rows:", len(roadworks))
print("CRS:", roadworks.crs)

print("Columns:")
print(roadworks.columns.tolist())

print("\nFirst rows:")
print(roadworks.head())


# VBB Static GTFS
print("\n" + "=" * 60)
print("4. VBB GTFS")
print("=" * 60)

gtfs_path = RAW_DIR / "gtfs" / "GTFS.zip"

with zipfile.ZipFile(gtfs_path) as gtfs_zip:

    print("Files inside GTFS:")
    print(gtfs_zip.namelist())

    files_to_check = [
        "agency.txt",
        "stops.txt",
        "routes.txt",
        "trips.txt",
        "calendar.txt",
        "calendar_dates.txt",
        "stop_times.txt",
    ]

    for filename in files_to_check:

        if filename not in gtfs_zip.namelist():
            print(f"\n{filename}: NOT FOUND")
            continue

        print("\n" + "-" * 40)
        print(filename)
        print("-" * 40)

        # Read only a few rows from each table.
        # stop_times.txt is intentionally not loaded in full during inspection.
        sample = pd.read_csv(
            gtfs_zip.open(filename),
            nrows=5,
            low_memory=False,
        )

        print("Columns:")
        print(sample.columns.tolist())

        print("Sample:")
        print(sample)


print("\n" + "=" * 60)
print("Inspection finished.")
print("=" * 60)