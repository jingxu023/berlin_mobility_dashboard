"""
Prepare the Berlin cycling counter data used in the dashboard.

Reads station metadata and annual hourly worksheets, matches historical
station IDs, assigns counters to districts, and creates hourly, daily
and data-quality outputs.
"""

from pathlib import Path
import calendar
import re

import geopandas as gpd
import pandas as pd


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

CYCLING_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "cycling"
    / "gesamtdatei-stundenwerte.xlsx"
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


# Years included in the source workbook
YEARS = range(2012, 2026)


# Match station IDs stored in worksheet headers.
#
# Examples:
# 02-MI-JAN-N
# 12-PA-SCH
# 05-FK-OBB-O
#
# Some headers also include the installation date, either
# on the same line or on the following line.
STATION_PATTERN = re.compile(
    r"^\d{2}-[A-Z]{2}-[A-Z0-9-]+"
)


# Historical station IDs
#
# Some older worksheets use IDs that differ from the current
# Standortdaten metadata. raw_station_id keeps the source value,
# while station_id is the ID used throughout the processed data.
STATION_ID_ALIASES = {
    "02-MI-AL-W": "01-MI-AL-W",
    "02-PA-SE-N": "11-PA-SE-N",
    "03-SP-NO-O": "16-SP-NO-O",
    "03-SP-NO-W": "16-SP-NO-W",
    "17-SZ-BRE-O": "17-SK-BRE-O",
    "17-SZ-BRE-W": "17-SK-BRE-W",
}


# Helper functions
def extract_station_id(value):
    """
    Extract a station ID from an Excel header.

    Examples
    --------
    '02-MI-JAN-N 01.04.2015'
        -> '02-MI-JAN-N'

    '05-FK-OBB-O\\n01.06.2015'
        -> '05-FK-OBB-O'
    """

    if pd.isna(value):
        return None

    text = str(value).strip()

    match = STATION_PATTERN.match(text)

    if match is None:
        return None

    return match.group(0)


def expected_hours_in_year(year):
    """
    Return the number of calendar hours in a year.

    Leap year:
        366 * 24 = 8784

    Normal year:
        365 * 24 = 8760

    This value is used only as a diagnostic benchmark.
    """

    days = (
        366
        if calendar.isleap(year)
        else 365
    )

    return days * 24


# Check required input files
if not CYCLING_PATH.exists():
    raise FileNotFoundError(
        f"Cycling workbook not found:\n"
        f"{CYCLING_PATH}"
    )

if not DISTRICT_PATH.exists():
    raise FileNotFoundError(
        f"Processed Berlin district file not found:\n"
        f"{DISTRICT_PATH}\n\n"
        "Run scripts/03_prepare_boundaries.py first."
    )


# Load station metadata
print("\n" + "=" * 70)
print("1. LOADING CYCLING STATION METADATA")
print("=" * 70)

stations = pd.read_excel(
    CYCLING_PATH,
    sheet_name="Standortdaten",
    header=0,
    engine="openpyxl",
)

print("\nOriginal columns:")
print(stations.columns.tolist())


# Rename station fields
stations = stations.rename(
    columns={
        "Zählstelle": "station_id",
        "Beschreibung - Fahrtrichtung": "station_name",
        "Breitengrad": "latitude",
        "Längengrad": "longitude",
        "Installationsdatum": "installed_at",
    }
)


required_station_columns = [
    "station_id",
    "station_name",
    "latitude",
    "longitude",
    "installed_at",
]


missing_columns = [
    column
    for column in required_station_columns
    if column not in stations.columns
]


if missing_columns:
    raise ValueError(
        "Missing station metadata columns:\n"
        + "\n".join(missing_columns)
    )


# Clean station metadata
stations["station_id"] = (
    stations["station_id"]
    .astype("string")
    .str.strip()
)

stations["station_name"] = (
    stations["station_name"]
    .astype("string")
    .str.strip()
)

stations["latitude"] = (
    pd.to_numeric(
        stations["latitude"],
        errors="coerce",
    )
)

stations["longitude"] = (
    pd.to_numeric(
        stations["longitude"],
        errors="coerce",
    )
)

stations["installed_at"] = (
    pd.to_datetime(
        stations["installed_at"],
        errors="coerce",
    )
)


# Remove metadata rows without a station ID.
stations = stations.dropna(
    subset=["station_id"]
)

stations = stations[
    stations["station_id"].str.len() > 0
].copy()


# Each station ID should appear only once in the metadata.
duplicate_metadata_ids = (
    stations["station_id"]
    .duplicated(
        keep=False
    )
)


if duplicate_metadata_ids.any():

    print(
        "\nWARNING: duplicated station IDs "
        "found in Standortdaten:"
    )

    print(
        stations.loc[
            duplicate_metadata_ids,
            [
                "station_id",
                "station_name",
            ],
        ].to_string(index=False)
    )

    raise ValueError(
        "Station metadata contains duplicate IDs."
    )


print(
    "\nStations after cleaning:",
    len(stations),
)

print(
    "Missing latitude:",
    stations["latitude"]
    .isna()
    .sum(),
)

print(
    "Missing longitude:",
    stations["longitude"]
    .isna()
    .sum(),
)

print(
    "Missing installation date:",
    stations["installed_at"]
    .isna()
    .sum(),
)


# Check that every alias points to an ID in the current metadata.
metadata_station_ids = set(
    stations["station_id"]
    .dropna()
    .tolist()
)


invalid_alias_targets = {
    raw_id: canonical_id
    for raw_id, canonical_id
    in STATION_ID_ALIASES.items()
    if canonical_id not in metadata_station_ids
}


if invalid_alias_targets:

    print(
        "\nWARNING: the following alias targets "
        "do not exist in Standortdaten:"
    )

    for raw_id, canonical_id in (
        invalid_alias_targets.items()
    ):
        print(
            f"  {raw_id} -> {canonical_id}"
        )

    raise ValueError(
        "Station alias configuration "
        "contains invalid target IDs."
    )


# Create station geometries
stations_with_coordinates = (
    stations.dropna(
        subset=[
            "latitude",
            "longitude",
        ]
    )
    .copy()
)


stations_geo = gpd.GeoDataFrame(
    stations_with_coordinates,
    geometry=gpd.points_from_xy(
        stations_with_coordinates[
            "longitude"
        ],
        stations_with_coordinates[
            "latitude"
        ],
    ),
    crs="EPSG:4326",
)


# Load district boundaries
print("\n" + "=" * 70)
print("2. ASSIGNING CYCLING STATIONS TO BERLIN DISTRICTS")
print("=" * 70)

districts = gpd.read_file(
    DISTRICT_PATH
)


if districts.crs is None:
    raise ValueError(
        "Berlin district GeoJSON has no CRS."
    )


if districts.crs.to_epsg() != 4326:

    districts = districts.to_crs(
        "EPSG:4326"
    )


required_district_columns = [
    "district_code",
    "district_name",
    "geometry",
]


missing_district_columns = [
    column
    for column in required_district_columns
    if column not in districts.columns
]


if missing_district_columns:

    raise ValueError(
        "District file is missing fields:\n"
        + "\n".join(
            missing_district_columns
        )
    )


# Assign each cycling counter to a Berlin district.
stations_geo = gpd.sjoin(
    stations_geo,
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


stations_geo = stations_geo.drop(
    columns=["index_right"],
    errors="ignore",
)


print(
    "\nStations with coordinates:",
    len(stations_geo),
)

print(
    "Stations without district:",
    stations_geo[
        "district_name"
    ]
    .isna()
    .sum(),
)


if stations_geo[
    "district_name"
].isna().any():

    print(
        "\nStations that could not be "
        "assigned to a district:"
    )

    print(
        stations_geo.loc[
            stations_geo[
                "district_name"
            ].isna(),
            [
                "station_id",
                "station_name",
                "latitude",
                "longitude",
            ],
        ].to_string(
            index=False
        )
    )


# Prepare metadata used when observations are joined later.
station_attributes = (
    stations_geo.drop(
        columns="geometry"
    )[
        [
            "station_id",
            "station_name",
            "latitude",
            "longitude",
            "installed_at",
            "district_code",
            "district_name",
        ]
    ]
    .copy()
)


known_station_ids = set(
    station_attributes[
        "station_id"
    ]
    .dropna()
    .tolist()
)


# Process annual worksheets
print("\n" + "=" * 70)
print("3. PROCESSING YEARLY CYCLING DATA")
print("=" * 70)


all_years = []

all_raw_station_ids = set()

all_canonical_station_ids = set()

year_quality_records = []


for year in YEARS:

    sheet_name = (
        f"Jahresdatei {year}"
    )

    print(
        f"\nProcessing {sheet_name}..."
    )


    # Load the worksheet as raw rows.
    raw = pd.read_excel(
        CYCLING_PATH,
        sheet_name=sheet_name,
        header=None,
        engine="openpyxl",
    )


    if raw.empty:

        print(
            "  WARNING: empty sheet."
        )

        continue


    # The first physical row contains the column headers.
    header = raw.iloc[0]

    # Data rows begin below the header.
    data = raw.iloc[1:].copy()


    # Check the timestamp column.
    timestamp_column = 0


    parsed_timestamp = pd.to_datetime(
        data[
            timestamp_column
        ],
        errors="coerce",
    )


    timestamp_valid_ratio = (
        parsed_timestamp
        .notna()
        .mean()
    )


    print(
        "  timestamp valid ratio:",
        f"{timestamp_valid_ratio:.2%}",
    )


    if timestamp_valid_ratio < 0.5:

        raise ValueError(
            f"Could not identify timestamp column "
            f"in {sheet_name}."
        )


    # Identify the columns that contain cycling counters.
    station_columns = {}


    for column in raw.columns:

        station_id = extract_station_id(
            header[column]
        )


        if station_id is None:
            continue


        station_columns[
            column
        ] = station_id


        all_raw_station_ids.add(
            station_id
        )


    print(
        "  station columns:",
        len(station_columns),
    )


    if len(station_columns) == 0:

        raise ValueError(
            f"No station columns found "
            f"in {sheet_name}."
        )


    # Keep the timestamp and counter columns.
    selected_columns = [
        timestamp_column,
        *station_columns.keys(),
    ]


    yearly = (
        data[
            selected_columns
        ]
        .copy()
    )


    yearly = yearly.rename(
        columns={
            timestamp_column:
                "timestamp",
            **station_columns,
        }
    )


    # Parse timestamps and remove rows without a valid timestamp.
    yearly[
        "timestamp"
    ] = pd.to_datetime(
        yearly[
            "timestamp"
        ],
        errors="coerce",
    )


    yearly = yearly.dropna(
        subset=["timestamp"]
    )


    # Jahresdatei 2012 contains timestamps from both 2012 and 2013.
    # Restrict every worksheet to the year in its sheet name so that
    # 2013 observations are not counted twice.
    timestamp_rows_before = len(
        yearly
    )


    actual_years_before = sorted(
        yearly[
            "timestamp"
        ]
        .dt.year
        .unique()
        .tolist()
    )


    yearly = yearly[
        yearly[
            "timestamp"
        ]
        .dt.year
        == year
    ].copy()


    removed_wrong_year = (
        timestamp_rows_before
        - len(yearly)
    )


    print(
        "  years found in source:",
        actual_years_before,
    )


    if removed_wrong_year > 0:

        print(
            f"  WARNING: removed "
            f"{removed_wrong_year:,} timestamp rows "
            f"outside calendar year {year}"
        )


    if yearly.empty:

        raise ValueError(
            f"No observations remain "
            f"for calendar year {year}."
        )


    remaining_years = (
        yearly[
            "timestamp"
        ]
        .dt.year
        .unique()
        .tolist()
    )


    if remaining_years != [year]:

        raise ValueError(
            f"{sheet_name} contains unexpected "
            f"years after filtering: "
            f"{remaining_years}"
        )


    # Compare source timestamps with the number of hours in the calendar year.
    unique_timestamp_count = (
        yearly[
            "timestamp"
        ]
        .nunique()
    )


    expected_calendar_hours = (
        expected_hours_in_year(
            year
        )
    )


    print(
        "  timestamps:",
        f"{unique_timestamp_count:,}",
    )

    print(
        "  calendar benchmark:",
        f"{expected_calendar_hours:,}",
    )


    # Convert the worksheet from wide to long format.
    yearly = yearly.melt(
        id_vars=[
            "timestamp"
        ],
        var_name="raw_station_id",
        value_name="count",
    )


    yearly[
        "raw_station_id"
    ] = (
        yearly[
            "raw_station_id"
        ]
        .astype("string")
        .str.strip()
    )


    # Map historical IDs to the current station IDs.
    yearly[
        "station_id"
    ] = (
        yearly[
            "raw_station_id"
        ]
        .replace(
            STATION_ID_ALIASES
        )
    )


    all_canonical_station_ids.update(
        yearly[
            "station_id"
        ]
        .dropna()
        .unique()
        .tolist()
    )


    # Convert cycling counts to numeric values.
    yearly[
        "count"
    ] = pd.to_numeric(
        yearly[
            "count"
        ],
        errors="coerce",
    )


    # Negative counts are not valid cycling observations.
    negative_mask = (
        yearly[
            "count"
        ]
        < 0
    )


    negative_count = (
        negative_mask.sum()
    )


    if negative_count > 0:

        print(
            f"  WARNING: "
            f"{negative_count:,} "
            f"negative counts converted to NaN"
        )

        yearly.loc[
            negative_mask,
            "count",
        ] = pd.NA


    yearly[
        "source_year"
    ] = year


    # Aliasing two historical IDs to the same current ID could create
    # duplicate station/timestamp records, so check after the mapping.
    duplicate_mask = (
        yearly.duplicated(
            subset=[
                "timestamp",
                "station_id",
            ],
            keep=False,
        )
    )


    duplicate_count = (
        duplicate_mask.sum()
    )


    if duplicate_count > 0:

        print(
            "\nDUPLICATE OBSERVATIONS "
            "FOUND AFTER ID HARMONISATION:"
        )

        print(
            yearly.loc[
                duplicate_mask,
                [
                    "timestamp",
                    "raw_station_id",
                    "station_id",
                    "count",
                ],
            ]
            .head(30)
            .to_string(
                index=False
            )
        )

        raise ValueError(
            f"{duplicate_count:,} duplicate "
            f"timestamp + station observations "
            f"found in {sheet_name}."
        )


    # Record basic quality statistics for this year.
    observed_rows = (
        yearly[
            "count"
        ]
        .notna()
        .sum()
    )


    missing_rows = (
        yearly[
            "count"
        ]
        .isna()
        .sum()
    )


    print(
        "  long-format rows:",
        f"{len(yearly):,}",
    )

    print(
        "  observed:",
        f"{observed_rows:,}",
    )

    print(
        "  missing:",
        f"{missing_rows:,}",
    )


    year_quality_records.append(
        {
            "year": year,
            "station_columns":
                len(
                    station_columns
                ),
            "unique_timestamps":
                unique_timestamp_count,
            "calendar_benchmark_hours":
                expected_calendar_hours,
            "timestamp_difference":
                unique_timestamp_count
                - expected_calendar_hours,
            "rows":
                len(
                    yearly
                ),
            "observed_rows":
                observed_rows,
            "missing_rows":
                missing_rows,
            "source_years":
                ",".join(
                    str(x)
                    for x
                    in actual_years_before
                ),
            "out_of_year_timestamps_removed":
                removed_wrong_year,
        }
    )


    all_years.append(
        yearly
    )


# Combine annual data
print("\n" + "=" * 70)
print("4. COMBINING 2012–2025")
print("=" * 70)


if not all_years:
    raise ValueError(
        "No cycling observations were loaded."
    )


cycling = pd.concat(
    all_years,
    ignore_index=True,
)


print(
    "\nCombined rows:",
    f"{len(cycling):,}",
)


# Check for duplicates across all years.
global_duplicate_mask = (
    cycling.duplicated(
        subset=[
            "timestamp",
            "station_id",
        ],
        keep=False,
    )
)


global_duplicate_count = (
    global_duplicate_mask.sum()
)


print(
    "Duplicate timestamp + station rows:",
    f"{global_duplicate_count:,}",
)


if global_duplicate_count > 0:

    print(
        cycling.loc[
            global_duplicate_mask,
            [
                "timestamp",
                "source_year",
                "raw_station_id",
                "station_id",
                "count",
            ],
        ]
        .head(50)
        .to_string(
            index=False
        )
    )


    raise ValueError(
        "Duplicate observations remain "
        "after combining yearly sheets."
    )


# Compare station IDs found in the worksheets with the metadata.
raw_ids_missing_metadata = sorted(
    all_raw_station_ids
    - known_station_ids
)


canonical_ids_missing_metadata = sorted(
    all_canonical_station_ids
    - known_station_ids
)


print(
    "\nRaw station IDs detected:",
    len(
        all_raw_station_ids
    ),
)

print(
    "Canonical station IDs detected:",
    len(
        all_canonical_station_ids
    ),
)

print(
    "Metadata station IDs:",
    len(
        known_station_ids
    ),
)


print(
    "\nRaw IDs not directly present "
    "in Standortdaten:",
    len(
        raw_ids_missing_metadata
    ),
)


for station_id in (
    raw_ids_missing_metadata
):
    canonical = (
        STATION_ID_ALIASES
        .get(
            station_id,
            station_id,
        )
    )

    print(
        f"  {station_id}"
        f" -> {canonical}"
    )


print(
    "\nCanonical IDs still missing metadata:",
    len(
        canonical_ids_missing_metadata
    ),
)


if canonical_ids_missing_metadata:

    for station_id in (
        canonical_ids_missing_metadata
    ):
        print(
            "  ",
            station_id,
        )


# Join cycling observations with station metadata.
cycling = cycling.merge(
    station_attributes,
    on="station_id",
    how="left",
    validate="many_to_one",
)


# Add time fields used in later analysis.
cycling[
    "date"
] = (
    cycling[
        "timestamp"
    ]
    .dt.normalize()
)


cycling[
    "year"
] = (
    cycling[
        "timestamp"
    ]
    .dt.year
)


cycling[
    "month"
] = (
    cycling[
        "timestamp"
    ]
    .dt.month
)


cycling[
    "month_name"
] = (
    cycling[
        "timestamp"
    ]
    .dt.month_name()
)


cycling[
    "quarter"
] = (
    cycling[
        "timestamp"
    ]
    .dt.quarter
)


cycling[
    "hour"
] = (
    cycling[
        "timestamp"
    ]
    .dt.hour
)


cycling[
    "day_of_week"
] = (
    cycling[
        "timestamp"
    ]
    .dt.dayofweek
)


cycling[
    "weekday"
] = (
    cycling[
        "timestamp"
    ]
    .dt.day_name()
)


cycling[
    "day_type"
] = (
    cycling[
        "day_of_week"
    ]
    .map(
        lambda day:
        "Weekend"
        if day >= 5
        else "Weekday"
    )
)


# Classify missing observations using the counter installation date.
print("\n" + "=" * 70)
print("5. CLASSIFYING DATA AVAILABILITY")
print("=" * 70)


cycling[
    "data_status"
] = "Observed"


missing_count_mask = (
    cycling[
        "count"
    ]
    .isna()
)


missing_metadata_mask = (
    cycling[
        "installed_at"
    ]
    .isna()
)


not_installed_mask = (
    missing_count_mask
    & cycling[
        "installed_at"
    ]
    .notna()
    & (
        cycling[
            "timestamp"
        ]
        < cycling[
            "installed_at"
        ]
    )
)


missing_observation_mask = (
    missing_count_mask
    & cycling[
        "installed_at"
    ]
    .notna()
    & (
        cycling[
            "timestamp"
        ]
        >= cycling[
            "installed_at"
        ]
    )
)


unknown_mask = (
    missing_count_mask
    & missing_metadata_mask
)


cycling.loc[
    not_installed_mask,
    "data_status",
] = "Not installed"


cycling.loc[
    missing_observation_mask,
    "data_status",
] = "Missing observation"


cycling.loc[
    unknown_mask,
    "data_status",
] = "Unknown"


print(
    "\nData-status distribution:"
)

print(
    cycling[
        "data_status"
    ]
    .value_counts(
        dropna=False
    )
)


# Mark rows where the counter had already been installed.
cycling[
    "expected_observation"
] = (
    cycling[
        "installed_at"
    ]
    .notna()
    & (
        cycling[
            "timestamp"
        ]
        >= cycling[
            "installed_at"
        ]
    )
)


# Sort the hourly output.
cycling = (
    cycling.sort_values(
        [
            "timestamp",
            "station_id",
        ]
    )
    .reset_index(
        drop=True
    )
)


# Create daily counter totals and coverage fields.
print("\n" + "=" * 70)
print("6. CREATING DAILY AGGREGATION")
print("=" * 70)


cycling[
    "observed_flag"
] = (
    cycling[
        "count"
    ]
    .notna()
    .astype(
        int
    )
)


cycling[
    "expected_flag"
] = (
    cycling[
        "expected_observation"
    ]
    .astype(
        int
    )
)


daily = (
    cycling.groupby(
        [
            "date",
            "station_id",
            "station_name",
            "latitude",
            "longitude",
            "installed_at",
            "district_code",
            "district_name",
        ],
        dropna=False,
    )
    .agg(
        daily_count=(
            "count",
            lambda series:
            series.sum(
                min_count=1
            )
        ),
        observed_hours=(
            "observed_flag",
            "sum",
        ),
        expected_hours=(
            "expected_flag",
            "sum",
        ),
        source_rows=(
            "timestamp",
            "size",
        ),
    )
    .reset_index()
)


# Calculate daily observation coverage.
daily[
    "coverage_ratio"
] = pd.NA


has_expected_hours = (
    daily[
        "expected_hours"
    ]
    > 0
)


daily.loc[
    has_expected_hours,
    "coverage_ratio",
] = (
    daily.loc[
        has_expected_hours,
        "observed_hours",
    ]
    /
    daily.loc[
        has_expected_hours,
        "expected_hours",
    ]
)


daily[
    "coverage_ratio"
] = pd.to_numeric(
    daily[
        "coverage_ratio"
    ],
    errors="coerce",
)


# Keep a simple daily quality category for later analysis.
daily[
    "coverage_status"
] = "Not active"


daily.loc[
    daily[
        "expected_hours"
    ]
    > 0,
    "coverage_status",
] = "Low coverage"


daily.loc[
    daily[
        "coverage_ratio"
    ]
    >= 0.90,
    "coverage_status",
] = "Usable"


daily.loc[
    daily[
        "coverage_ratio"
    ]
    >= 0.99,
    "coverage_status",
] = "Complete"


# Add daily time fields.
daily[
    "year"
] = (
    daily[
        "date"
    ]
    .dt.year
)


daily[
    "month"
] = (
    daily[
        "date"
    ]
    .dt.month
)


daily[
    "month_name"
] = (
    daily[
        "date"
    ]
    .dt.month_name()
)


daily[
    "quarter"
] = (
    daily[
        "date"
    ]
    .dt.quarter
)


daily[
    "day_of_week"
] = (
    daily[
        "date"
    ]
    .dt.dayofweek
)


daily[
    "weekday"
] = (
    daily[
        "date"
    ]
    .dt.day_name()
)


daily[
    "day_type"
] = (
    daily[
        "day_of_week"
    ]
    .map(
        lambda day:
        "Weekend"
        if day >= 5
        else "Weekday"
    )
)


# Build the yearly data-quality summary.
year_quality = pd.DataFrame(
    year_quality_records
)


yearly_observation_summary = (
    cycling.groupby(
        "year"
    )
    .agg(
        total_rows=(
            "count",
            "size",
        ),
        observed_rows=(
            "observed_flag",
            "sum",
        ),
        expected_rows=(
            "expected_flag",
            "sum",
        ),
        unique_stations=(
            "station_id",
            "nunique",
        ),
        unique_timestamps=(
            "timestamp",
            "nunique",
        ),
    )
    .reset_index()
)


yearly_observation_summary[
    "expected_coverage_ratio"
] = (
    yearly_observation_summary[
        "observed_rows"
    ]
    /
    yearly_observation_summary[
        "expected_rows"
    ]
)


year_quality = year_quality.merge(
    yearly_observation_summary,
    on="year",
    how="left",
)


# Prepare station outputs.
station_output = (
    stations_geo[
        [
            "station_id",
            "station_name",
            "latitude",
            "longitude",
            "installed_at",
            "district_code",
            "district_name",
            "geometry",
        ]
    ]
    .copy()
)


# Remove helper columns that are not part of the hourly output.
cycling = cycling.drop(
    columns=[
        "observed_flag",
        "expected_flag",
    ],
    errors="ignore",
)


# Output paths
hourly_path = (
    OUTPUT_DIR
    / "cycling_hourly.parquet"
)

daily_path = (
    OUTPUT_DIR
    / "cycling_daily.parquet"
)

station_path = (
    OUTPUT_DIR
    / "cycling_stations.parquet"
)

station_geojson_path = (
    OUTPUT_DIR
    / "cycling_stations.geojson"
)

quality_path = (
    OUTPUT_DIR
    / "cycling_quality_by_year.parquet"
)


# Save processed datasets
print("\n" + "=" * 70)
print("7. SAVING PROCESSED DATA")
print("=" * 70)


cycling.to_parquet(
    hourly_path,
    index=False,
    engine="pyarrow",
)


daily.to_parquet(
    daily_path,
    index=False,
    engine="pyarrow",
)


station_output.drop(
    columns="geometry"
).to_parquet(
    station_path,
    index=False,
    engine="pyarrow",
)


station_output.to_file(
    station_geojson_path,
    driver="GeoJSON",
)


year_quality.to_parquet(
    quality_path,
    index=False,
    engine="pyarrow",
)


# Final quality report
print("\n" + "=" * 70)
print("CYCLING DATA PREPARED SUCCESSFULLY")
print("=" * 70)


print(
    "\nHourly rows:",
    f"{len(cycling):,}",
)


print(
    "Daily rows:",
    f"{len(daily):,}",
)


print(
    "Unique canonical stations:",
    cycling[
        "station_id"
    ]
    .nunique(),
)


print(
    "Unique raw station IDs:",
    cycling[
        "raw_station_id"
    ]
    .nunique(),
)


print(
    "Stations with metadata:",
    cycling.loc[
        cycling[
            "station_name"
        ]
        .notna(),
        "station_id",
    ]
    .nunique(),
)


print(
    "Stations without metadata:",
    cycling.loc[
        cycling[
            "station_name"
        ]
        .isna(),
        "station_id",
    ]
    .nunique(),
)


print(
    "Stations without district:",
    cycling.loc[
        cycling[
            "district_name"
        ]
        .isna(),
        "station_id",
    ]
    .nunique(),
)


print(
    "\nDate range:"
)

print(
    cycling[
        "timestamp"
    ]
    .min(),
    "→",
    cycling[
        "timestamp"
    ]
    .max(),
)


print(
    "\nObserved counts:",
    f"{cycling['count'].notna().sum():,}",
)


print(
    "Missing counts:",
    f"{cycling['count'].isna().sum():,}",
)


print(
    "\nData-status distribution:"
)

print(
    cycling[
        "data_status"
    ]
    .value_counts(
        dropna=False
    )
)


print(
    "\nDaily coverage status:"
)

print(
    daily[
        "coverage_status"
    ]
    .value_counts(
        dropna=False
    )
)


print(
    "\nYearly quality summary:"
)

display_columns = [
    "year",
    "unique_timestamps_y",
    "unique_stations",
    "observed_rows",
    "expected_rows",
    "expected_coverage_ratio",
    "out_of_year_timestamps_removed",
]


# The merged timestamp column may or may not receive a suffix,
# depending on the pandas merge result.
available_display_columns = [
    column
    for column in display_columns
    if column in year_quality.columns
]


if (
    "unique_timestamps"
    in year_quality.columns
    and "unique_timestamps_y"
    not in year_quality.columns
):
    available_display_columns.insert(
        1,
        "unique_timestamps",
    )


print(
    year_quality[
        available_display_columns
    ]
    .to_string(
        index=False
    )
)


print(
    "\nSaved files:"
)

print(
    f"  {hourly_path}"
)

print(
    f"  {daily_path}"
)

print(
    f"  {station_path}"
)

print(
    f"  {station_geojson_path}"
)

print(
    f"  {quality_path}"
)


print(
    "\nDone."
)