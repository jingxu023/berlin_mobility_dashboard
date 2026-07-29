"""
Prepare the VBB GTFS data used in the Berlin dashboard.

Filters the regional feed to Berlin, groups routes into transport modes,
combines platform records into stop areas, and calculates scheduled
service by hour.
"""

from pathlib import Path
import zipfile

import geopandas as gpd
import numpy as np
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

GTFS_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "gtfs"
    / "GTFS.zip"
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
STOPS_PATH = (
    OUTPUT_DIR
    / "gtfs_berlin_stops.parquet"
)

STATIONS_PATH = (
    OUTPUT_DIR
    / "gtfs_berlin_stations.parquet"
)

STATIONS_GEOJSON_PATH = (
    OUTPUT_DIR
    / "gtfs_berlin_stations.geojson"
)

ROUTES_PATH = (
    OUTPUT_DIR
    / "gtfs_berlin_routes.parquet"
)

TRIPS_PATH = (
    OUTPUT_DIR
    / "gtfs_berlin_trips.parquet"
)

SERVICE_HOUR_PATH = (
    OUTPUT_DIR
    / "gtfs_berlin_service_by_hour.parquet"
)

ROUTE_SERVICE_HOUR_PATH = (
    OUTPUT_DIR
    / "gtfs_berlin_route_service_by_hour.parquet"
)

QUALITY_PATH = (
    OUTPUT_DIR
    / "gtfs_berlin_quality_summary.parquet"
)


# Processing settings
CHUNK_SIZE = 500_000

WEEKDAY_COLS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def classify_mode(route_type, route_short_name):
    """
    Map GTFS route types to the transport modes used in the dashboard.

    VBB uses extended route-type values in addition to the standard
    GTFS codes. Important values in this feed include:

        100 / 106 -> Regional Rail
        109       -> S-Bahn
        400       -> U-Bahn
        700       -> Bus
        900       -> Tram
        1000      -> Ferry
    """

    try:
        route_type = int(route_type)

    except (TypeError, ValueError):
        return "Other"

    short_name = (
        ""
        if pd.isna(route_short_name)
        else str(route_short_name).strip()
    )

    # Standard GTFS route types
    if route_type == 0:
        return "Tram"

    if route_type == 1:
        return "U-Bahn"

    if route_type == 2:

        if short_name.upper().startswith("S"):
            return "S-Bahn"

        return "Regional Rail"

    if route_type == 3:
        return "Bus"

    if route_type == 4:
        return "Ferry"

    # VBB extended route types
    if route_type in {100, 106}:
        return "Regional Rail"

    if route_type == 109:
        return "S-Bahn"

    if route_type == 400:
        return "U-Bahn"

    if route_type == 700:
        return "Bus"

    if route_type == 900:
        return "Tram"

    if route_type == 1000:
        return "Ferry"

    # Fallback ranges for other extended route types
    if 100 <= route_type < 200:
        return "Regional Rail"

    if 400 <= route_type < 500:
        return "U-Bahn"

    if 700 <= route_type < 800:
        return "Bus"

    if 900 <= route_type < 1000:
        return "Tram"

    if 1000 <= route_type < 1100:
        return "Ferry"

    return "Other"


def derive_stop_area_id(stop_id, parent_station):
    """
    Derive one stop-area ID for related GTFS stop records.

    parent_station is used where available. VBB platform IDs such as

        de:11000:900160004:3:54

    are otherwise reduced to

        de:11000:900160004

    so individual platform records are not counted as separate
    physical stop areas.
    """

    if pd.notna(parent_station):

        parent = str(
            parent_station
        ).strip()

        if parent:
            return parent

    if pd.isna(stop_id):
        return pd.NA

    stop_id = str(
        stop_id
    ).strip()

    parts = stop_id.split(":")

    if (
        len(parts) >= 3
        and parts[0] == "de"
    ):
        return ":".join(
            parts[:3]
        )

    return stop_id


def most_common(series):
    """Return the most common non-null value."""

    clean = series.dropna()

    if clean.empty:
        return pd.NA

    values = clean.mode()

    if values.empty:
        return clean.iloc[0]

    return values.iloc[0]


def safe_parent_value(
    lookup,
    parent_id,
    column,
):
    """Read a value from the full stops table using a parent stop ID."""

    if pd.isna(parent_id):
        return None

    parent_id = str(
        parent_id
    ).strip()

    if parent_id not in lookup.index:
        return None

    row = lookup.loc[
        parent_id
    ]

    if isinstance(
        row,
        pd.DataFrame,
    ):
        row = row.iloc[0]

    value = row.get(
        column
    )

    if pd.isna(value):
        return None

    return value


def build_service_weekday_weights(
    calendar_df,
    calendar_dates,
):
    """
    Calculate weekday service weights for each service_id.

    calendar.txt provides the regular weekly schedule and
    calendar_dates.txt adds or removes service on specific dates.

    A weight of 1 means the service runs on every occurrence of that
    weekday in the feed period. A weight of 0.5 means it runs on half
    of them.

    These weights allow scheduled service to be summarised without
    expanding stop_times.txt separately for every calendar date.
    """

    calendar_df = (
        calendar_df.copy()
    )

    calendar_dates = (
        calendar_dates.copy()
    )

    # Clean weekday flags
    for column in WEEKDAY_COLS:

        calendar_df[
            column
        ] = (
            pd.to_numeric(
                calendar_df[
                    column
                ],
                errors="coerce",
            )
            .fillna(0)
            .astype("int8")
        )

    # Parse service dates
    calendar_df[
        "start_date"
    ] = pd.to_datetime(
        calendar_df[
            "start_date"
        ].astype(str),
        format="%Y%m%d",
        errors="coerce",
    )

    calendar_df[
        "end_date"
    ] = pd.to_datetime(
        calendar_df[
            "end_date"
        ].astype(str),
        format="%Y%m%d",
        errors="coerce",
    )

    calendar_dates[
        "date"
    ] = pd.to_datetime(
        calendar_dates[
            "date"
        ].astype(str),
        format="%Y%m%d",
        errors="coerce",
    )

    calendar_dates[
        "exception_type"
    ] = pd.to_numeric(
        calendar_dates[
            "exception_type"
        ],
        errors="coerce",
    ).astype("Int64")

    # Determine the full date range covered by the feed.
    start_candidates = [
        calendar_df[
            "start_date"
        ].min(),

        calendar_dates[
            "date"
        ].min(),
    ]

    end_candidates = [
        calendar_df[
            "end_date"
        ].max(),

        calendar_dates[
            "date"
        ].max(),
    ]

    start_candidates = [
        value
        for value
        in start_candidates
        if pd.notna(value)
    ]

    end_candidates = [
        value
        for value
        in end_candidates
        if pd.notna(value)
    ]

    feed_start = min(
        start_candidates
    )

    feed_end = max(
        end_candidates
    )

    # Build the calendar dates covered by the feed.
    days = pd.DataFrame(
        {
            "date":
                pd.date_range(
                    feed_start,
                    feed_end,
                    freq="D",
                )
        }
    )

    days[
        "day_of_week"
    ] = (
        days[
            "date"
        ]
        .dt.dayofweek
    )

    # Expand each service over the feed date range.
    # The resulting table is small enough for this feed.
    expanded = (
        calendar_df.merge(
            days,
            how="cross",
        )
    )

    in_range = (
        (
            expanded[
                "date"
            ]
            >=
            expanded[
                "start_date"
            ]
        )
        &
        (
            expanded[
                "date"
            ]
            <=
            expanded[
                "end_date"
            ]
        )
    )

    # Determine whether each service normally runs on each date.
    base_active = np.zeros(
        len(expanded),
        dtype=np.int8,
    )

    for weekday_number, weekday_column in enumerate(
        WEEKDAY_COLS
    ):

        mask = (
            expanded[
                "day_of_week"
            ]
            ==
            weekday_number
        )

        base_active[
            mask.to_numpy()
        ] = (
            expanded.loc[
                mask,
                weekday_column,
            ]
            .to_numpy(
                dtype=np.int8
            )
        )

    base_services = expanded.loc[
        in_range
        &
        (
            base_active == 1
        ),
        [
            "service_id",
            "date",
        ],
    ].copy()

    # Apply additions and removals from calendar_dates.txt.
    base_index = (
        pd.MultiIndex.from_frame(
            base_services
        )
    )

    additions = (
        calendar_dates.loc[
            calendar_dates[
                "exception_type"
            ]
            == 1,
            [
                "service_id",
                "date",
            ],
        ]
        .dropna()
    )

    removals = (
        calendar_dates.loc[
            calendar_dates[
                "exception_type"
            ]
            == 2,
            [
                "service_id",
                "date",
            ],
        ]
        .dropna()
    )

    additions_index = (
        pd.MultiIndex.from_frame(
            additions
        )
    )

    removals_index = (
        pd.MultiIndex.from_frame(
            removals
        )
    )

    active_index = (
        base_index
        .union(
            additions_index
        )
        .difference(
            removals_index
        )
    )

    active_dates = (
        active_index.to_frame(
            index=False
        )
    )

    active_dates.columns = [
        "service_id",
        "date",
    ]

    active_dates[
        "day_of_week"
    ] = (
        active_dates[
            "date"
        ]
        .dt.dayofweek
    )

    # Number of Mondays, Tuesdays and other weekdays in the feed period.
    weekday_denominators = (
        days.groupby(
            "day_of_week"
        )
        .size()
        .to_dict()
    )

    # Count active dates for each service and weekday.
    active_counts = (
        active_dates.groupby(
            [
                "service_id",
                "day_of_week",
            ]
        )
        .size()
        .rename(
            "active_days"
        )
        .reset_index()
    )

    active_counts[
        "weekday_weight"
    ] = [
        row.active_days
        /
        weekday_denominators[
            int(
                row.day_of_week
            )
        ]
        for row
        in active_counts.itertuples()
    ]

    # Store one set of weekday weights per service_id.
    weights = (
        active_counts.pivot(
            index="service_id",
            columns="day_of_week",
            values="weekday_weight",
        )
        .reindex(
            columns=range(7),
            fill_value=0,
        )
        .fillna(0)
    )

    weights.columns = [
        f"{weekday}_weight"
        for weekday
        in WEEKDAY_COLS
    ]

    weights = (
        weights.reset_index()
    )

    # Keep the total number of active dates as a separate quality field.
    total_active_days = (
        active_dates.groupby(
            "service_id"
        )
        .size()
        .rename(
            "active_days_total"
        )
        .reset_index()
    )

    weights = weights.merge(
        total_active_days,
        on="service_id",
        how="left",
        validate="one_to_one",
    )

    return (
        weights,
        active_dates,
        feed_start,
        feed_end,
    )


# Check required input files
if not GTFS_PATH.exists():
    raise FileNotFoundError(
        f"GTFS.zip not found:\n"
        f"{GTFS_PATH}"
    )

if not DISTRICT_PATH.exists():
    raise FileNotFoundError(
        f"Berlin district file not found:\n"
        f"{DISTRICT_PATH}\n\n"
        "Run scripts/03_prepare_boundaries.py first."
    )


# Load core GTFS tables
print(
    "\n"
    + "=" * 70
)

print(
    "1. LOADING VBB STATIC GTFS"
)

print(
    "=" * 70
)


with zipfile.ZipFile(
    GTFS_PATH
) as gtfs_zip:

    stops = pd.read_csv(
        gtfs_zip.open(
            "stops.txt"
        ),
        dtype={
            "stop_id":
                "string",

            "stop_code":
                "string",

            "stop_name":
                "string",

            "parent_station":
                "string",

            "platform_code":
                "string",

            "zone_id":
                "string",

            "level_id":
                "string",
        },
        low_memory=False,
    )

    routes = pd.read_csv(
        gtfs_zip.open(
            "routes.txt"
        ),
        dtype={
            "route_id":
                "string",

            "agency_id":
                "string",

            "route_short_name":
                "string",

            "route_long_name":
                "string",
        },
        low_memory=False,
    )

    trips = pd.read_csv(
        gtfs_zip.open(
            "trips.txt"
        ),
        dtype={
            "route_id":
                "string",

            "service_id":
                "string",

            "trip_id":
                "string",

            "shape_id":
                "string",
        },
        low_memory=False,
    )

    calendar_df = pd.read_csv(
        gtfs_zip.open(
            "calendar.txt"
        ),
        dtype={
            "service_id":
                "string",
        },
        low_memory=False,
    )

    calendar_dates = pd.read_csv(
        gtfs_zip.open(
            "calendar_dates.txt"
        ),
        dtype={
            "service_id":
                "string",
        },
        low_memory=False,
    )


print(
    "VBB stop records:",
    f"{len(stops):,}",
)

print(
    "VBB routes:",
    f"{len(routes):,}",
)

print(
    "VBB trips:",
    f"{len(trips):,}",
)


# Clean stop coordinates
stops[
    "stop_lat"
] = pd.to_numeric(
    stops[
        "stop_lat"
    ],
    errors="coerce",
)

stops[
    "stop_lon"
] = pd.to_numeric(
    stops[
        "stop_lon"
    ],
    errors="coerce",
)

stops[
    "location_type"
] = (
    pd.to_numeric(
        stops[
            "location_type"
        ],
        errors="coerce",
    )
    .astype(
        "Int64"
    )
)


valid_stops = (
    stops.dropna(
        subset=[
            "stop_lat",
            "stop_lon",
        ]
    )
    .copy()
)


print(
    "Stops with coordinates:",
    f"{len(valid_stops):,}",
)


# Convert stops to point geometries.
stops_geo = gpd.GeoDataFrame(
    valid_stops,
    geometry=gpd.points_from_xy(
        valid_stops[
            "stop_lon"
        ],
        valid_stops[
            "stop_lat"
        ],
    ),
    crs="EPSG:4326",
)


# Load Berlin district boundaries
districts = gpd.read_file(
    DISTRICT_PATH
)

if districts.crs is None:

    raise ValueError(
        "Berlin district file has no CRS."
    )

if districts.crs.to_epsg() != 4326:

    districts = (
        districts.to_crs(
            "EPSG:4326"
        )
    )


# Keep stop records whose coordinates fall within Berlin.
print(
    "\n"
    + "=" * 70
)

print(
    "2. FILTERING GTFS STOPS TO BERLIN"
)

print(
    "=" * 70
)


berlin_stops_all = (
    gpd.sjoin(
        stops_geo,
        districts[
            [
                "district_code",
                "district_name",
                "geometry",
            ]
        ],
        how="inner",
        predicate="within",
    )
)


berlin_stops_all = (
    berlin_stops_all.drop(
        columns=[
            "index_right"
        ],
        errors="ignore",
    )
)


print(
    "Spatially matched Berlin stop records:",
    f"{len(berlin_stops_all):,}",
)


berlin_stop_ids = set(
    berlin_stops_all[
        "stop_id"
    ]
    .dropna()
    .tolist()
)


# Classify route types
routes[
    "route_type"
] = (
    pd.to_numeric(
        routes[
            "route_type"
        ],
        errors="coerce",
    )
    .astype(
        "Int64"
    )
)


routes[
    "mode"
] = [
    classify_mode(
        route_type,
        route_name,
    )
    for route_type, route_name
    in zip(
        routes[
            "route_type"
        ],
        routes[
            "route_short_name"
        ],
    )
]


print(
    "\nAll VBB routes by mode:"
)

print(
    routes[
        "mode"
    ]
    .value_counts()
)


# Build service-calendar weights
print(
    "\n"
    + "=" * 70
)

print(
    "3. BUILDING GTFS SERVICE CALENDAR"
)

print(
    "=" * 70
)


(
    service_weights,
    active_service_dates,
    feed_start,
    feed_end,
) = build_service_weekday_weights(
    calendar_df,
    calendar_dates,
)


print(
    "Feed validity:",
    feed_start,
    "→",
    feed_end,
)

print(
    "Active service-date combinations:",
    f"{len(active_service_dates):,}",
)


# Join trip, route and service information.
trip_lookup = (
    trips.merge(
        routes[
            [
                "route_id",
                "route_short_name",
                "route_long_name",
                "route_type",
                "mode",
            ]
        ],
        on="route_id",
        how="left",
        validate="many_to_one",
    )
)


trip_lookup = (
    trip_lookup.merge(
        service_weights,
        on="service_id",
        how="left",
        validate="many_to_one",
    )
)


weight_columns = [
    f"{weekday}_weight"
    for weekday
    in WEEKDAY_COLS
]


for column in weight_columns:

    trip_lookup[
        column
    ] = (
        trip_lookup[
            column
        ]
        .fillna(0)
    )


# Stop-to-district lookup used while reading stop_times.
stop_district_lookup = (
    berlin_stops_all[
        [
            "stop_id",
            "district_code",
            "district_name",
        ]
    ]
    .drop_duplicates(
        subset=[
            "stop_id"
        ]
    )
)


# Process stop_times.txt in chunks to avoid loading the full table at once.
print(
    "\n"
    + "=" * 70
)

print(
    "4. PROCESSING STOP_TIMES IN CHUNKS"
)

print(
    "=" * 70
)


total_stop_time_rows = 0

berlin_stop_time_rows = 0

invalid_gtfs_times = 0

after_midnight_rows = 0

served_stop_ids = set()

relevant_trip_ids = set()

route_hour_parts = []


with zipfile.ZipFile(
    GTFS_PATH
) as gtfs_zip:

    reader = pd.read_csv(
        gtfs_zip.open(
            "stop_times.txt"
        ),
        dtype={
            "trip_id":
                "string",

            "stop_id":
                "string",

            "arrival_time":
                "string",

            "departure_time":
                "string",
        },
        chunksize=CHUNK_SIZE,
        low_memory=False,
    )


    for chunk_number, chunk in enumerate(
        reader,
        start=1,
    ):

        total_stop_time_rows += (
            len(chunk)
        )


        # Keep only stop-time records belonging to Berlin stops.
        chunk = (
            chunk[
                chunk[
                    "stop_id"
                ]
                .isin(
                    berlin_stop_ids
                )
            ]
            .copy()
        )


        berlin_stop_time_rows += (
            len(chunk)
        )


        if chunk.empty:

            print(
                f"Chunk {chunk_number}: "
                "0 Berlin rows"
            )

            continue


        served_stop_ids.update(
            chunk[
                "stop_id"
            ]
            .dropna()
            .tolist()
        )


        relevant_trip_ids.update(
            chunk[
                "trip_id"
            ]
            .dropna()
            .tolist()
        )


        # Add district fields.
        chunk = chunk.merge(
            stop_district_lookup,
            on="stop_id",
            how="left",
            validate="many_to_one",
        )


        # Add trip, route and service fields.
        trip_columns = [
            "trip_id",
            "route_id",
            "route_short_name",
            "route_long_name",
            "route_type",
            "mode",
            "service_id",
            *weight_columns,
        ]


        chunk = chunk.merge(
            trip_lookup[
                trip_columns
            ],
            on="trip_id",
            how="left",
            validate="many_to_one",
        )


        # Prefer departure_time and use arrival_time when it is missing.
        chunk[
            "analysis_time"
        ] = (
            chunk[
                "departure_time"
            ]
            .fillna(
                chunk[
                    "arrival_time"
                ]
            )
        )


        hour_text = (
            chunk[
                "analysis_time"
            ]
            .astype(
                "string"
            )
            .str.extract(
                r"^(\d{1,3}):",
                expand=False,
            )
        )


        chunk[
            "raw_hour"
        ] = pd.to_numeric(
            hour_text,
            errors="coerce",
        )


        invalid_gtfs_times += (
            chunk[
                "raw_hour"
            ]
            .isna()
            .sum()
        )


        chunk = chunk.dropna(
            subset=[
                "raw_hour",
                "route_id",
            ]
        )


        chunk[
            "raw_hour"
        ] = (
            chunk[
                "raw_hour"
            ]
            .astype(int)
        )


        after_midnight_rows += (
            chunk[
                "raw_hour"
            ]
            .gt(23)
            .sum()
        )


        chunk[
            "service_day_offset"
        ] = (
            chunk[
                "raw_hour"
            ]
            // 24
        )


        chunk[
            "hour"
        ] = (
            chunk[
                "raw_hour"
            ]
            % 24
        )


        # GTFS times may continue beyond 24:00.
        # For example, Monday 25:00 belongs to Tuesday 01:00
        # when the hourly profile is displayed by clock day.
        for source_day_number, source_day in enumerate(
            WEEKDAY_COLS
        ):

            weight_column = (
                f"{source_day}_weight"
            )


            temp = (
                chunk[
                    chunk[
                        weight_column
                    ]
                    > 0
                ]
                .copy()
            )


            if temp.empty:
                continue


            temp[
                "target_weekday_number"
            ] = (
                (
                    source_day_number
                    +
                    temp[
                        "service_day_offset"
                    ]
                )
                % 7
            )


            temp[
                "weekday"
            ] = (
                temp[
                    "target_weekday_number"
                ]
                .map(
                    dict(
                        enumerate(
                            WEEKDAY_NAMES
                        )
                    )
                )
            )


            temp[
                "avg_scheduled_stop_departures"
            ] = (
                temp[
                    weight_column
                ]
            )


            grouped = (
                temp.groupby(
                    [
                        "weekday",
                        "hour",
                        "district_code",
                        "district_name",
                        "mode",
                        "route_id",
                        "route_short_name",
                    ],
                    dropna=False,
                )
                [
                    "avg_scheduled_stop_departures"
                ]
                .sum()
                .reset_index()
            )


            route_hour_parts.append(
                grouped
            )


        print(
            f"Chunk {chunk_number}: "
            f"{len(chunk):,} usable Berlin rows"
        )


# Combine route-level hourly summaries from all chunks.
print(
    "\n"
    + "=" * 70
)

print(
    "5. CREATING SERVICE INTENSITY SUMMARIES"
)

print(
    "=" * 70
)


if route_hour_parts:

    route_service_hour = (
        pd.concat(
            route_hour_parts,
            ignore_index=True,
        )
    )


    route_service_hour = (
        route_service_hour.groupby(
            [
                "weekday",
                "hour",
                "district_code",
                "district_name",
                "mode",
                "route_id",
                "route_short_name",
            ],
            dropna=False,
        )
        [
            "avg_scheduled_stop_departures"
        ]
        .sum()
        .reset_index()
    )


else:

    route_service_hour = (
        pd.DataFrame()
    )


# Aggregate route-level values to district/mode/hour.
if not route_service_hour.empty:

    service_hour = (
        route_service_hour.groupby(
            [
                "weekday",
                "hour",
                "district_code",
                "district_name",
                "mode",
            ],
            dropna=False,
        )
        [
            "avg_scheduled_stop_departures"
        ]
        .sum()
        .reset_index()
    )


else:

    service_hour = (
        pd.DataFrame()
    )


# Keep Berlin stop records that are actually referenced by stop_times.
berlin_stops = (
    berlin_stops_all[
        berlin_stops_all[
            "stop_id"
        ]
        .isin(
            served_stop_ids
        )
    ]
    .copy()
)


print(
    "\nBerlin stop records used by stop_times:",
    f"{len(berlin_stops):,}",
)


# Build canonical stop-area IDs.
print(
    "\n"
    + "=" * 70
)

print(
    "6. BUILDING BERLIN STOP-AREA ENTITIES"
)

print(
    "=" * 70
)


berlin_stops[
    "station_id"
] = [
    derive_stop_area_id(
        stop_id,
        parent_station,
    )
    for stop_id, parent_station
    in zip(
        berlin_stops[
            "stop_id"
        ],
        berlin_stops[
            "parent_station"
        ],
    )
]


# Full stop table lookup for parent-station names and coordinates.
full_stop_lookup = (
    stops.drop_duplicates(
        subset=[
            "stop_id"
        ]
    )
    .set_index(
        "stop_id",
        drop=False,
    )
)


# Combine platform and stop records into stop-area entities.
station_records = []


for station_id, group in (
    berlin_stops.groupby(
        "station_id",
        dropna=False,
        sort=False,
    )
):

    # Use a parent station ID when one is available.
    parent_ids = (
        group[
            "parent_station"
        ]
        .dropna()
        .astype(str)
        .str.strip()
    )


    parent_ids = (
        parent_ids[
            parent_ids != ""
        ]
    )


    if not parent_ids.empty:

        parent_id = (
            parent_ids.iloc[0]
        )

    else:

        parent_id = (
            station_id
        )


    # Prefer the parent station name.
    parent_name = safe_parent_value(
        full_stop_lookup,
        parent_id,
        "stop_name",
    )


    if parent_name is not None:

        station_name = (
            parent_name
        )

    else:

        station_name = most_common(
            group[
                "stop_name"
            ]
        )


    # Prefer parent station coordinates, otherwise use the component mean.
    parent_lat = safe_parent_value(
        full_stop_lookup,
        parent_id,
        "stop_lat",
    )

    parent_lon = safe_parent_value(
        full_stop_lookup,
        parent_id,
        "stop_lon",
    )


    if parent_lat is not None:

        latitude = (
            pd.to_numeric(
                parent_lat,
                errors="coerce",
            )
        )

    else:

        latitude = (
            group[
                "stop_lat"
            ]
            .mean()
        )


    if parent_lon is not None:

        longitude = (
            pd.to_numeric(
                parent_lon,
                errors="coerce",
            )
        )

    else:

        longitude = (
            group[
                "stop_lon"
            ]
            .mean()
        )


    # Keep the most common component district as a fallback.
    fallback_district_code = (
        most_common(
            group[
                "district_code"
            ]
        )
    )

    fallback_district_name = (
        most_common(
            group[
                "district_name"
            ]
        )
    )


    # Number of source GTFS stop records represented by this stop area.
    stop_record_count = (
        group[
            "stop_id"
        ]
        .nunique()
    )


    # Count location_type 0 stop/platform records.
    platform_count = (
        pd.to_numeric(
            group[
                "location_type"
            ],
            errors="coerce",
        )
        .fillna(0)
        .eq(0)
        .sum()
    )


    station_records.append(
        {
            "station_id":
                station_id,

            "station_name":
                station_name,

            "latitude":
                latitude,

            "longitude":
                longitude,

            "stop_record_count":
                stop_record_count,

            "platform_count":
                int(
                    platform_count
                ),

            "uses_parent_station":
                bool(
                    group[
                        "parent_station"
                    ]
                    .notna()
                    .any()
                ),

            "fallback_district_code":
                fallback_district_code,

            "fallback_district_name":
                fallback_district_name,
        }
    )


stations_berlin = pd.DataFrame(
    station_records
)


stations_berlin[
    "latitude"
] = pd.to_numeric(
    stations_berlin[
        "latitude"
    ],
    errors="coerce",
)


stations_berlin[
    "longitude"
] = pd.to_numeric(
    stations_berlin[
        "longitude"
    ],
    errors="coerce",
)


print(
    "Canonical Berlin stop-area entities:",
    f"{len(stations_berlin):,}",
)


# Convert stop areas to point geometries.
station_coordinate_data = (
    stations_berlin.dropna(
        subset=[
            "latitude",
            "longitude",
        ]
    )
    .copy()
)


stations_geo = gpd.GeoDataFrame(
    station_coordinate_data,
    geometry=gpd.points_from_xy(
        station_coordinate_data[
            "longitude"
        ],
        station_coordinate_data[
            "latitude"
        ],
    ),
    crs="EPSG:4326",
)


# Assign stop areas to Berlin districts.
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


stations_geo = (
    stations_geo.drop(
        columns=[
            "index_right"
        ],
        errors="ignore",
    )
)


# Use the component stop-record district if the stop-area point
# could not be assigned spatially.
stations_geo[
    "district_code"
] = (
    stations_geo[
        "district_code"
    ]
    .fillna(
        stations_geo[
            "fallback_district_code"
        ]
    )
)


stations_geo[
    "district_name"
] = (
    stations_geo[
        "district_name"
    ]
    .fillna(
        stations_geo[
            "fallback_district_name"
        ]
    )
)


# Keep trips that serve at least one Berlin stop.
berlin_trips = (
    trip_lookup[
        trip_lookup[
            "trip_id"
        ]
        .isin(
            relevant_trip_ids
        )
    ]
    .copy()
)


print(
    "Trips serving Berlin:",
    f"{len(berlin_trips):,}",
)


# Keep routes used by the Berlin trips.
berlin_route_ids = set(
    berlin_trips[
        "route_id"
    ]
    .dropna()
    .tolist()
)


berlin_routes = (
    routes[
        routes[
            "route_id"
        ]
        .isin(
            berlin_route_ids
        )
    ]
    .copy()
)


# Count trips for each Berlin route.
trip_counts = (
    berlin_trips.groupby(
        "route_id"
    )
    [
        "trip_id"
    ]
    .nunique()
    .rename(
        "trip_count"
    )
    .reset_index()
)


berlin_routes = (
    berlin_routes.merge(
        trip_counts,
        on="route_id",
        how="left",
        validate="one_to_one",
    )
)


print(
    "Routes serving Berlin:",
    f"{len(berlin_routes):,}",
)


# Prepare stop-level output.
stop_output_columns = [
    "stop_id",
    "stop_code",
    "stop_name",
    "stop_lat",
    "stop_lon",
    "location_type",
    "parent_station",
    "platform_code",
    "wheelchair_boarding",
    "zone_id",
    "level_id",
    "station_id",
    "district_code",
    "district_name",
]


stop_output_columns = [
    column
    for column
    in stop_output_columns
    if column
    in berlin_stops.columns
]


berlin_stop_output = (
    berlin_stops[
        stop_output_columns
    ]
    .copy()
)


# Prepare stop-area output.
station_output_columns = [
    "station_id",
    "station_name",
    "latitude",
    "longitude",
    "stop_record_count",
    "platform_count",
    "uses_parent_station",
    "district_code",
    "district_name",
    "geometry",
]


station_output_columns = [
    column
    for column
    in station_output_columns
    if column
    in stations_geo.columns
]


station_output = (
    stations_geo[
        station_output_columns
    ]
    .copy()
)


# Build the data-quality summary.
other_routes = (
    berlin_routes[
        "mode"
    ]
    .eq(
        "Other"
    )
    .sum()
)


stations_without_district = (
    station_output[
        "district_name"
    ]
    .isna()
    .sum()
)


stations_without_coordinates = (
    stations_berlin[
        [
            "latitude",
            "longitude",
        ]
    ]
    .isna()
    .any(
        axis=1
    )
    .sum()
)


service_ids_without_weights = (
    berlin_trips[
        berlin_trips[
            "active_days_total"
        ]
        .isna()
    ]
    [
        "service_id"
    ]
    .nunique()
)


quality_summary = pd.DataFrame(
    [
        {
            "metric":
                "vbb_stop_records",
            "value":
                len(stops),
        },

        {
            "metric":
                "spatial_berlin_stop_records",
            "value":
                len(
                    berlin_stops_all
                ),
        },

        {
            "metric":
                "berlin_service_stop_records",
            "value":
                len(
                    berlin_stops
                ),
        },

        {
            "metric":
                "canonical_stop_area_entities",
            "value":
                len(
                    stations_berlin
                ),
        },

        {
            "metric":
                "stations_without_district",
            "value":
                stations_without_district,
        },

        {
            "metric":
                "stations_without_coordinates",
            "value":
                stations_without_coordinates,
        },

        {
            "metric":
                "vbb_routes",
            "value":
                len(routes),
        },

        {
            "metric":
                "berlin_routes",
            "value":
                len(
                    berlin_routes
                ),
        },

        {
            "metric":
                "berlin_routes_classified_other",
            "value":
                other_routes,
        },

        {
            "metric":
                "vbb_trips",
            "value":
                len(trips),
        },

        {
            "metric":
                "berlin_trips",
            "value":
                len(
                    berlin_trips
                ),
        },

        {
            "metric":
                "total_stop_time_rows",
            "value":
                total_stop_time_rows,
        },

        {
            "metric":
                "berlin_stop_time_rows",
            "value":
                berlin_stop_time_rows,
        },

        {
            "metric":
                "invalid_gtfs_times",
            "value":
                invalid_gtfs_times,
        },

        {
            "metric":
                "after_midnight_gtfs_times",
            "value":
                after_midnight_rows,
        },

        {
            "metric":
                "calendar_exception_rows",
            "value":
                len(
                    calendar_dates
                ),
        },

        {
            "metric":
                "service_ids_without_weights",
            "value":
                service_ids_without_weights,
        },
    ]
)


# Save processed outputs
print(
    "\n"
    + "=" * 70
)

print(
    "7. SAVING PROCESSED GTFS DATA"
)

print(
    "=" * 70
)


berlin_stop_output.to_parquet(
    STOPS_PATH,
    index=False,
    engine="pyarrow",
)


station_output.drop(
    columns=[
        "geometry"
    ],
    errors="ignore",
).to_parquet(
    STATIONS_PATH,
    index=False,
    engine="pyarrow",
)


station_output.to_file(
    STATIONS_GEOJSON_PATH,
    driver="GeoJSON",
)


berlin_routes.to_parquet(
    ROUTES_PATH,
    index=False,
    engine="pyarrow",
)


berlin_trips.to_parquet(
    TRIPS_PATH,
    index=False,
    engine="pyarrow",
)


service_hour.to_parquet(
    SERVICE_HOUR_PATH,
    index=False,
    engine="pyarrow",
)


route_service_hour.to_parquet(
    ROUTE_SERVICE_HOUR_PATH,
    index=False,
    engine="pyarrow",
)


quality_summary.to_parquet(
    QUALITY_PATH,
    index=False,
    engine="pyarrow",
)


# Final report
print(
    "\n"
    + "=" * 70
)

print(
    "GTFS DATA PREPARED SUCCESSFULLY"
)

print(
    "=" * 70
)


print(
    "\nVBB stop records:",
    f"{len(stops):,}",
)

print(
    "Spatial Berlin stop records:",
    f"{len(berlin_stops_all):,}",
)

print(
    "Berlin service stop records:",
    f"{len(berlin_stops):,}",
)

print(
    "Canonical stop-area entities:",
    f"{len(stations_berlin):,}",
)


print(
    "\nTrips serving Berlin:",
    f"{len(berlin_trips):,}",
)

print(
    "Routes serving Berlin:",
    f"{len(berlin_routes):,}",
)


print(
    "\nRoutes by transport mode:"
)

print(
    berlin_routes[
        "mode"
    ]
    .value_counts(
        dropna=False
    )
)


print(
    "\nStop areas by district:"
)

print(
    station_output[
        "district_name"
    ]
    .value_counts(
        dropna=False
    )
)


print(
    "\nBerlin stop-time rows:",
    f"{berlin_stop_time_rows:,}",
)

print(
    "After-midnight GTFS times:",
    f"{after_midnight_rows:,}",
)

print(
    "Invalid GTFS times:",
    f"{invalid_gtfs_times:,}",
)


print(
    "\nFeed validity:"
)

print(
    feed_start,
    "→",
    feed_end,
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

for path in [
    STOPS_PATH,
    STATIONS_PATH,
    STATIONS_GEOJSON_PATH,
    ROUTES_PATH,
    TRIPS_PATH,
    SERVICE_HOUR_PATH,
    ROUTE_SERVICE_HOUR_PATH,
    QUALITY_PATH,
]:

    print(
        f"  {path}"
    )


print(
    "\nIMPORTANT:"
)

print(
    "avg_scheduled_stop_departures is a transit-service "
    "intensity measure, not passenger volume."
)


print(
    "\nDone."
)