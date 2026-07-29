"""
Prepare the Berlin road disruption data used in the dashboard.

Parses event dates, assigns event status and districts, creates map points,
and saves the processed roadworks and quality-summary files.
"""

from pathlib import Path
import ast
import json

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


# Check Parquet dependency
try:
    import pyarrow  # noqa: F401
except ImportError as exc:
    raise ImportError(
        "\npyarrow is required to save Parquet files.\n"
        "Install it first with:\n\n"
        "    python -m pip install pyarrow\n"
    ) from exc


# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]

ROADWORKS_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "roadworks"
    / "baustellen_sperrungen_viz.json"
)

DISTRICT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "berlin_bezirke.geojson"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# Output files
PARQUET_PATH = (
    OUTPUT_DIR
    / "roadworks.parquet"
)

GEOJSON_PATH = (
    OUTPUT_DIR
    / "roadworks.geojson"
)

MAP_GEOJSON_PATH = (
    OUTPUT_DIR
    / "roadworks_map_points.geojson"
)

QUALITY_PATH = (
    OUTPUT_DIR
    / "roadworks_quality_summary.parquet"
)


# Helper functions
def parse_validity(value):
    """
    Convert the validity field to a Python dictionary.

    Expected examples:

    {
        "from": "2025-07-23T07:00",
        "to": "2026-08-17T17:00"
    }

    or:

    {
        "from": "2024-05-14T12:00",
        "to": None
    }
    """

    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    if pd.isna(value):
        return {}

    if isinstance(value, str):
        text = value.strip()

        if not text:
            return {}

        # Try JSON first.
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Some readers may return the field as a Python-style dict string.
        try:
            parsed = ast.literal_eval(text)

            if isinstance(parsed, dict):
                return parsed

        except (ValueError, SyntaxError):
            pass

    return {}


def extract_map_point(geometry):
    """
    Return a point that can be used for the dashboard map.

    Point geometries are kept as they are. For GeometryCollections,
    the first Point is used when one is available. Other geometry types
    fall back to representative_point().
    """

    if geometry is None:
        return None

    if geometry.is_empty:
        return None

    if geometry.geom_type == "Point":
        return geometry

    if geometry.geom_type == "GeometryCollection":

        for geom in geometry.geoms:

            if (
                geom is not None
                and not geom.is_empty
                and geom.geom_type == "Point"
            ):
                return geom

    try:
        return geometry.representative_point()

    except Exception:
        return None


def classify_status(start_time, end_time, reference_time):
    """
    Classify an event as Future, Active, Expired or Unknown
    using its start and end times.
    """

    if pd.isna(start_time):
        return "Unknown"

    if start_time > reference_time:
        return "Future"

    if pd.isna(end_time):
        return "Active"

    if end_time >= reference_time:
        return "Active"

    return "Expired"


# Check required input files
if not ROADWORKS_PATH.exists():
    raise FileNotFoundError(
        f"Roadworks file not found:\n"
        f"{ROADWORKS_PATH}"
    )

if not DISTRICT_PATH.exists():
    raise FileNotFoundError(
        f"Berlin district file not found:\n"
        f"{DISTRICT_PATH}\n\n"
        "Run scripts/03_prepare_boundaries.py first."
    )


# Load road disruption data
print("\n" + "=" * 70)
print("1. LOADING BERLIN ROAD DISRUPTION DATA")
print("=" * 70)

roadworks = gpd.read_file(
    ROADWORKS_PATH
)

print(
    "\nRows:",
    len(roadworks),
)

print(
    "CRS:",
    roadworks.crs,
)

print(
    "\nOriginal columns:"
)

print(
    roadworks.columns.tolist()
)


# Check CRS
if roadworks.crs is None:

    raise ValueError(
        "Roadworks dataset has no CRS."
    )


if roadworks.crs.to_epsg() != 4326:

    print(
        "\nConverting roadworks to EPSG:4326..."
    )

    roadworks = roadworks.to_crs(
        "EPSG:4326"
    )


# Keep the original geometry type for later checks.
roadworks[
    "geometry_type"
] = (
    roadworks.geometry
    .geom_type
)


print(
    "\nGeometry types:"
)

print(
    roadworks[
        "geometry_type"
    ]
    .value_counts(
        dropna=False
    )
)


# Clean text fields
string_columns = [
    "id",
    "lms_id",
    "tstore",
    "objectState",
    "subtype",
    "icon",
    "severity",
    "direction",
    "street",
    "section",
    "content",
]


for column in string_columns:

    if column not in roadworks.columns:
        continue

    roadworks[
        column
    ] = (
        roadworks[
            column
        ]
        .astype("string")
        .str.strip()
    )


# Rename fields used later in the project.
roadworks = roadworks.rename(
    columns={
        "subtype": "event_type",
        "objectState": "object_state",
    }
)


# Parse event validity dates
print("\n" + "=" * 70)
print("2. PARSING EVENT VALIDITY")
print("=" * 70)


validity_parsed = (
    roadworks[
        "validity"
    ]
    .apply(
        parse_validity
    )
)


roadworks[
    "start_time"
] = validity_parsed.apply(
    lambda value:
    value.get("from")
    if isinstance(value, dict)
    else None
)


roadworks[
    "end_time"
] = validity_parsed.apply(
    lambda value:
    value.get("to")
    if isinstance(value, dict)
    else None
)


roadworks[
    "start_time"
] = pd.to_datetime(
    roadworks[
        "start_time"
    ],
    errors="coerce",
)


roadworks[
    "end_time"
] = pd.to_datetime(
    roadworks[
        "end_time"
    ],
    errors="coerce",
)


print(
    "Missing start time:",
    roadworks[
        "start_time"
    ]
    .isna()
    .sum(),
)

print(
    "Missing end time:",
    roadworks[
        "end_time"
    ]
    .isna()
    .sum(),
)


# Calculate event duration
roadworks[
    "duration_hours"
] = (
    roadworks[
        "end_time"
    ]
    - roadworks[
        "start_time"
    ]
).dt.total_seconds() / 3600


roadworks[
    "duration_days"
] = (
    roadworks[
        "duration_hours"
    ]
    / 24
)


invalid_duration_mask = (
    roadworks[
        "duration_hours"
    ]
    < 0
)


print(
    "Negative event durations:",
    invalid_duration_mask.sum(),
)


if invalid_duration_mask.any():

    roadworks.loc[
        invalid_duration_mask,
        [
            "duration_hours",
            "duration_days",
        ],
    ] = pd.NA


# Determine event status using the current Berlin clock time.
# Source timestamps are stored without timezone information, so the
# reference time is converted to a naive local timestamp before comparison.
reference_time = (
    pd.Timestamp.now(
        tz="Europe/Berlin"
    )
    .tz_localize(None)
)


roadworks[
    "event_status"
] = [
    classify_status(
        start_time,
        end_time,
        reference_time,
    )
    for start_time, end_time
    in zip(
        roadworks[
            "start_time"
        ],
        roadworks[
            "end_time"
        ],
    )
]


print(
    "\nReference time:",
    reference_time,
)

print(
    "\nEvent status:"
)

print(
    roadworks[
        "event_status"
    ]
    .value_counts(
        dropna=False
    )
)


# Clean lane fields
for column in [
    "total_lanes",
    "closed_lanes",
]:

    if column not in roadworks.columns:
        roadworks[
            column
        ] = pd.NA

    roadworks[
        column
    ] = pd.to_numeric(
        roadworks[
            column
        ],
        errors="coerce",
    )


negative_total_lanes = (
    roadworks[
        "total_lanes"
    ]
    < 0
)

negative_closed_lanes = (
    roadworks[
        "closed_lanes"
    ]
    < 0
)


roadworks.loc[
    negative_total_lanes,
    "total_lanes",
] = pd.NA


roadworks.loc[
    negative_closed_lanes,
    "closed_lanes",
] = pd.NA


# Calculate the share of lanes recorded as closed.
roadworks[
    "closure_ratio"
] = pd.NA


valid_lane_ratio_mask = (
    roadworks[
        "total_lanes"
    ]
    .notna()
    &
    roadworks[
        "closed_lanes"
    ]
    .notna()
    &
    (
        roadworks[
            "total_lanes"
        ]
        > 0
    )
)


roadworks.loc[
    valid_lane_ratio_mask,
    "closure_ratio",
] = (
    roadworks.loc[
        valid_lane_ratio_mask,
        "closed_lanes",
    ]
    /
    roadworks.loc[
        valid_lane_ratio_mask,
        "total_lanes",
    ]
)


roadworks[
    "closure_ratio"
] = pd.to_numeric(
    roadworks[
        "closure_ratio"
    ],
    errors="coerce",
)


invalid_closure_ratio = (
    roadworks[
        "closure_ratio"
    ]
    > 1
)


print(
    "\nClosure ratios > 1:",
    invalid_closure_ratio.sum(),
)


# Keep ratios above 1 visible rather than correcting them automatically.


# Group the source severity values into dashboard closure categories.
roadworks[
    "closure_category"
] = "Unknown"


roadworks.loc[
    roadworks[
        "severity"
    ]
    == "keine Sperrung",
    "closure_category",
] = "No closure"


roadworks.loc[
    roadworks[
        "severity"
    ]
    == "Fahrtrichtungssperrung",
    "closure_category",
] = "Directional closure"


roadworks.loc[
    roadworks[
        "severity"
    ]
    == "Vollsperrung",
    "closure_category",
] = "Full closure"


# Create one point per event for the dashboard map.
print("\n" + "=" * 70)
print("3. GENERATING MAP LOCATIONS")
print("=" * 70)


roadworks[
    "map_geometry"
] = (
    roadworks.geometry
    .apply(
        extract_map_point
    )
)


missing_map_geometry = (
    roadworks[
        "map_geometry"
    ]
    .isna()
    .sum()
)


print(
    "Missing map points:",
    missing_map_geometry,
)


roadworks[
    "map_longitude"
] = roadworks[
    "map_geometry"
].apply(
    lambda geometry:
    geometry.x
    if geometry is not None
    else None
)


roadworks[
    "map_latitude"
] = roadworks[
    "map_geometry"
].apply(
    lambda geometry:
    geometry.y
    if geometry is not None
    else None
)


# Load Berlin district boundaries
districts = gpd.read_file(
    DISTRICT_PATH
)


if districts.crs is None:

    raise ValueError(
        "Berlin districts dataset has no CRS."
    )


if districts.crs.to_epsg() != 4326:

    districts = districts.to_crs(
        "EPSG:4326"
    )


# Build a point GeoDataFrame for district assignment.
roadworks_map = gpd.GeoDataFrame(
    roadworks.drop(
        columns=[
            "geometry",
        ]
    ).copy(),
    geometry="map_geometry",
    crs="EPSG:4326",
)


roadworks_map = roadworks_map.rename_geometry(
    "geometry"
)


# Assign events to Berlin districts.
print("\n" + "=" * 70)
print("4. ASSIGNING EVENTS TO BERLIN DISTRICTS")
print("=" * 70)


roadworks_map = gpd.sjoin(
    roadworks_map,
    districts[
        [
            "district_code",
            "district_name",
            "geometry",
        ]
    ],
    how="left",
    predicate="within",
)


roadworks_map = roadworks_map.drop(
    columns=[
        "index_right",
    ],
    errors="ignore",
)


print(
    "\nEvents without district:",
    roadworks_map[
        "district_name"
    ]
    .isna()
    .sum(),
)


if roadworks_map[
    "district_name"
].isna().any():

    print(
        "\nEvents without district:"
    )

    print(
        roadworks_map.loc[
            roadworks_map[
                "district_name"
            ]
            .isna(),
            [
                "id",
                "event_type",
                "street",
                "map_latitude",
                "map_longitude",
            ],
        ]
        .head(30)
        .to_string(
            index=False
        )
    )


# Add district fields back to the original-geometry data.
district_lookup = (
    roadworks_map[
        [
            "id",
            "district_code",
            "district_name",
        ]
    ]
    .drop_duplicates(
        subset=["id"],
        keep="first",
    )
)


roadworks = roadworks.merge(
    district_lookup,
    on="id",
    how="left",
    validate="many_to_one",
)


# Add map coordinates to the original dataset.
map_lookup = (
    roadworks_map[
        [
            "id",
            "map_longitude",
            "map_latitude",
        ]
    ]
    .drop_duplicates(
        subset=["id"],
        keep="first",
    )
)


roadworks = roadworks.drop(
    columns=[
        "map_longitude",
        "map_latitude",
    ],
    errors="ignore",
)


roadworks = roadworks.merge(
    map_lookup,
    on="id",
    how="left",
    validate="many_to_one",
)


# Add date fields used in later analysis.
roadworks[
    "start_date"
] = (
    roadworks[
        "start_time"
    ]
    .dt.normalize()
)


roadworks[
    "end_date"
] = (
    roadworks[
        "end_time"
    ]
    .dt.normalize()
)


roadworks[
    "start_year"
] = (
    roadworks[
        "start_time"
    ]
    .dt.year
)


roadworks[
    "start_month"
] = (
    roadworks[
        "start_time"
    ]
    .dt.month
)


roadworks[
    "start_month_name"
] = (
    roadworks[
        "start_time"
    ]
    .dt.month_name()
)


# Add Boolean fields used in dashboard filters and summaries.
roadworks[
    "is_full_closure"
] = (
    roadworks[
        "closure_category"
    ]
    == "Full closure"
)


roadworks[
    "is_directional_closure"
] = (
    roadworks[
        "closure_category"
    ]
    == "Directional closure"
)


roadworks[
    "is_active"
] = (
    roadworks[
        "event_status"
    ]
    == "Active"
)


roadworks[
    "is_future_event"
] = (
    roadworks[
        "event_status"
    ]
    == "Future"
)


# Check for duplicate event IDs.
duplicate_id_mask = (
    roadworks[
        "id"
    ]
    .duplicated(
        keep=False
    )
)


duplicate_id_count = (
    duplicate_id_mask.sum()
)


print(
    "\nDuplicate event IDs:",
    duplicate_id_count,
)


if duplicate_id_count > 0:

    print(
        roadworks.loc[
            duplicate_id_mask,
            [
                "id",
                "event_type",
                "street",
                "start_time",
                "end_time",
            ],
        ]
        .to_string(
            index=False
        )
    )


# Select fields for the main analysis table.
analysis_columns = [
    "id",
    "lms_id",
    "tstore",
    "object_state",
    "event_type",
    "severity",
    "closure_category",
    "direction",
    "street",
    "section",
    "content",
    "start_time",
    "end_time",
    "start_date",
    "end_date",
    "start_year",
    "start_month",
    "start_month_name",
    "duration_hours",
    "duration_days",
    "event_status",
    "is_active",
    "is_future_event",
    "is_full_closure",
    "is_directional_closure",
    "total_lanes",
    "closed_lanes",
    "closure_ratio",
    "district_code",
    "district_name",
    "map_longitude",
    "map_latitude",
    "geometry_type",
]


analysis_columns = [
    column
    for column in analysis_columns
    if column in roadworks.columns
]


roadworks_analysis = (
    roadworks[
        analysis_columns
    ]
    .copy()
)


# Build a small table of data-quality checks.
quality_summary = pd.DataFrame(
    [
        {
            "metric": "total_rows",
            "value": len(
                roadworks
            ),
        },
        {
            "metric": "missing_start_time",
            "value": roadworks[
                "start_time"
            ].isna().sum(),
        },
        {
            "metric": "missing_end_time",
            "value": roadworks[
                "end_time"
            ].isna().sum(),
        },
        {
            "metric": "missing_district",
            "value": roadworks[
                "district_name"
            ].isna().sum(),
        },
        {
            "metric": "missing_map_coordinates",
            "value": roadworks[
                "map_latitude"
            ].isna().sum(),
        },
        {
            "metric": "missing_total_lanes",
            "value": roadworks[
                "total_lanes"
            ].isna().sum(),
        },
        {
            "metric": "missing_closed_lanes",
            "value": roadworks[
                "closed_lanes"
            ].isna().sum(),
        },
        {
            "metric": "invalid_closure_ratio_gt_1",
            "value": invalid_closure_ratio.sum(),
        },
        {
            "metric": "duplicate_event_ids",
            "value": duplicate_id_count,
        },
    ]
)


# Save processed roadworks data
print("\n" + "=" * 70)
print("5. SAVING PROCESSED ROADWORKS DATA")
print("=" * 70)


roadworks_analysis.to_parquet(
    PARQUET_PATH,
    index=False,
    engine="pyarrow",
)


# Save the original event geometries.
# validity and the temporary map geometry are removed because they are
# not suitable fields for the GeoJSON output.
roadworks_geo = roadworks.drop(
    columns=[
        "validity",
        "map_geometry",
    ],
    errors="ignore",
).copy()


roadworks_geo = gpd.GeoDataFrame(
    roadworks_geo,
    geometry="geometry",
    crs="EPSG:4326",
)


roadworks_geo.to_file(
    GEOJSON_PATH,
    driver="GeoJSON",
)


# Save the point geometry used by the dashboard map.
map_output_columns = [
    "id",
    "event_type",
    "severity",
    "closure_category",
    "street",
    "section",
    "start_time",
    "end_time",
    "duration_days",
    "event_status",
    "total_lanes",
    "closed_lanes",
    "closure_ratio",
    "district_code",
    "district_name",
    "map_longitude",
    "map_latitude",
    "geometry",
]


map_output_columns = [
    column
    for column in map_output_columns
    if column in roadworks_map.columns
]


roadworks_map_output = (
    roadworks_map[
        map_output_columns
    ]
    .copy()
)


roadworks_map_output.to_file(
    MAP_GEOJSON_PATH,
    driver="GeoJSON",
)


# Save data-quality summary.
quality_summary.to_parquet(
    QUALITY_PATH,
    index=False,
    engine="pyarrow",
)


# Final report
print("\n" + "=" * 70)
print("ROADWORKS DATA PREPARED SUCCESSFULLY")
print("=" * 70)


print(
    "\nRows:",
    f"{len(roadworks):,}",
)


print(
    "\nEvent types:"
)

print(
    roadworks[
        "event_type"
    ]
    .value_counts(
        dropna=False
    )
)


print(
    "\nSeverity:"
)

print(
    roadworks[
        "severity"
    ]
    .value_counts(
        dropna=False
    )
)


print(
    "\nClosure category:"
)

print(
    roadworks[
        "closure_category"
    ]
    .value_counts(
        dropna=False
    )
)


print(
    "\nEvent status:"
)

print(
    roadworks[
        "event_status"
    ]
    .value_counts(
        dropna=False
    )
)


print(
    "\nEvents by district:"
)

print(
    roadworks[
        "district_name"
    ]
    .value_counts(
        dropna=False
    )
)


print(
    "\nGeometry types:"
)

print(
    roadworks[
        "geometry_type"
    ]
    .value_counts(
        dropna=False
    )
)


print(
    "\nMissing district:",
    roadworks[
        "district_name"
    ]
    .isna()
    .sum(),
)


print(
    "Missing map coordinates:",
    roadworks[
        "map_latitude"
    ]
    .isna()
    .sum(),
)


print(
    "Missing start time:",
    roadworks[
        "start_time"
    ]
    .isna()
    .sum(),
)


print(
    "Missing end time:",
    roadworks[
        "end_time"
    ]
    .isna()
    .sum(),
)


print(
    "\nDuration statistics (days):"
)

print(
    roadworks[
        "duration_days"
    ]
    .describe()
)


print(
    "\nQuality summary:"
)

print(
    quality_summary.to_string(
        index=False
    )
)


print(
    "\nSaved files:"
)

print(
    f"  {PARQUET_PATH}"
)

print(
    f"  {GEOJSON_PATH}"
)

print(
    f"  {MAP_GEOJSON_PATH}"
)

print(
    f"  {QUALITY_PATH}"
)


print(
    "\nReference time used for status:"
)

print(
    reference_time
)


print(
    "\nDone."
)