"""
Build the analytical tables used by the Berlin Mobility Dashboard.

Creates cycling quality and trend summaries, road disruption statistics,
public transport indicators, district-level tables and dashboard KPIs.
"""

from pathlib import Path
import json

import pandas as pd


# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]

PROCESSED_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)

ANALYTICS_DIR = (
    PROCESSED_DIR
    / "analytics"
)

ANALYTICS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# Input files
BOUNDARIES_PATH = (
    PROCESSED_DIR
    / "berlin_bezirke.geojson"
)

CYCLING_HOURLY_PATH = (
    PROCESSED_DIR
    / "cycling_hourly.parquet"
)

CYCLING_DAILY_PATH = (
    PROCESSED_DIR
    / "cycling_daily.parquet"
)

ROADWORKS_PATH = (
    PROCESSED_DIR
    / "roadworks.parquet"
)

GTFS_STATIONS_PATH = (
    PROCESSED_DIR
    / "gtfs_berlin_stations.parquet"
)

GTFS_SERVICE_PATH = (
    PROCESSED_DIR
    / "gtfs_berlin_service_by_hour.parquet"
)

GTFS_ROUTE_SERVICE_PATH = (
    PROCESSED_DIR
    / "gtfs_berlin_route_service_by_hour.parquet"
)


# Analysis settings

# A cycling day is usable when at least 90% of the
# expected hourly observations are available.
DAILY_COVERAGE_THRESHOLD = 0.90


# Use a fixed group of counters for the long-term trend.
# Comparing all available counters from 2012 onward would also
# capture the expansion of Berlin's monitoring network.
PANEL_START_YEAR = 2017
PANEL_END_YEAR = 2025


# Stable-panel counters must have been active for most of the year.
MIN_EXPECTED_ACTIVE_DAYS = 300


# At least 70% of active days must pass the daily coverage threshold.
MIN_USABLE_DAY_RATIO = 0.70


# Years used for the recent hourly cycling profile.
RECENT_PROFILE_START_YEAR = 2023
RECENT_PROFILE_END_YEAR = 2025


WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
]

WEEKENDS = [
    "Saturday",
    "Sunday",
]


# Output files
CYCLING_STATION_YEAR_QUALITY_PATH = (
    ANALYTICS_DIR
    / "cycling_station_year_quality.parquet"
)

CYCLING_PANEL_YEARLY_PATH = (
    ANALYTICS_DIR
    / "cycling_stable_panel_yearly.parquet"
)

CYCLING_PANEL_STATIONS_PATH = (
    ANALYTICS_DIR
    / "cycling_stable_panel_stations.parquet"
)

CYCLING_HOURLY_PROFILE_PATH = (
    ANALYTICS_DIR
    / "cycling_recent_hourly_profile.parquet"
)

CYCLING_DISTRICT_PATH = (
    ANALYTICS_DIR
    / "cycling_district_summary.parquet"
)

ROADWORKS_DISTRICT_PATH = (
    ANALYTICS_DIR
    / "roadworks_district_summary.parquet"
)

GTFS_DISTRICT_PATH = (
    ANALYTICS_DIR
    / "gtfs_district_summary.parquet"
)

GTFS_HOURLY_PATH = (
    ANALYTICS_DIR
    / "gtfs_hourly_profile.parquet"
)

DISTRICT_MOBILITY_PATH = (
    ANALYTICS_DIR
    / "district_mobility_summary.parquet"
)

KPI_SUMMARY_PATH = (
    ANALYTICS_DIR
    / "dashboard_kpi_summary.parquet"
)


# Helper functions
def section(title):
    print(
        "\n"
        + "=" * 72
    )

    print(title)

    print(
        "=" * 72
    )


def validate_file(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found:\n"
            f"{path}"
        )


def safe_divide(
    numerator,
    denominator,
):
    """Divide two values while handling missing or zero denominators."""

    if (
        denominator is None
        or pd.isna(denominator)
        or denominator == 0
    ):
        return pd.NA

    return (
        numerator
        / denominator
    )


# Check required processed files
for required_path in [
    BOUNDARIES_PATH,
    CYCLING_HOURLY_PATH,
    CYCLING_DAILY_PATH,
    ROADWORKS_PATH,
    GTFS_STATIONS_PATH,
    GTFS_SERVICE_PATH,
    GTFS_ROUTE_SERVICE_PATH,
]:

    validate_file(
        required_path
    )


# Load district properties directly from the processed GeoJSON.
section(
    "1. LOADING PROCESSED DATA"
)


with open(
    BOUNDARIES_PATH,
    "r",
    encoding="utf-8",
) as file:

    boundary_geojson = json.load(
        file
    )


district_records = []


for feature in boundary_geojson.get(
    "features",
    []
):

    properties = (
        feature.get(
            "properties",
            {}
        )
    )

    district_records.append(
        {
            "district_code":
                properties.get(
                    "district_code"
                ),

            "district_name":
                properties.get(
                    "district_name"
                ),
        }
    )


districts = (
    pd.DataFrame(
        district_records
    )
    .drop_duplicates()
)


if len(districts) != 12:

    print(
        "WARNING: expected 12 Berlin districts, "
        f"found {len(districts)}."
    )


# Load daily cycling data
cycling_daily_columns = [
    "date",
    "station_id",
    "station_name",
    "district_name",
    "daily_count",
    "observed_hours",
    "expected_hours",
    "coverage_ratio",
    "year",
    "month",
    "weekday",
    "day_type",
]


cycling_daily = pd.read_parquet(
    CYCLING_DAILY_PATH,
    columns=cycling_daily_columns,
)


# Load hourly cycling data
cycling_hourly_columns = [
    "timestamp",
    "station_id",
    "station_name",
    "district_name",
    "count",
    "year",
    "hour",
    "weekday",
    "day_type",
]


cycling_hourly = pd.read_parquet(
    CYCLING_HOURLY_PATH,
    columns=cycling_hourly_columns,
)


# Load road disruption data
roadworks = pd.read_parquet(
    ROADWORKS_PATH
)


# Load GTFS analytical inputs
gtfs_stations = pd.read_parquet(
    GTFS_STATIONS_PATH
)

gtfs_service = pd.read_parquet(
    GTFS_SERVICE_PATH
)

gtfs_route_service = pd.read_parquet(
    GTFS_ROUTE_SERVICE_PATH
)


print(
    "Berlin districts:",
    len(districts),
)

print(
    "Cycling daily rows:",
    f"{len(cycling_daily):,}",
)

print(
    "Cycling hourly rows:",
    f"{len(cycling_hourly):,}",
)

print(
    "Road disruption rows:",
    f"{len(roadworks):,}",
)

print(
    "GTFS stop areas:",
    f"{len(gtfs_stations):,}",
)

print(
    "GTFS service rows:",
    f"{len(gtfs_service):,}",
)


# Cycling daily data quality
section(
    "2. CYCLING DATA QUALITY"
)


cycling_daily[
    "expected_hours"
] = pd.to_numeric(
    cycling_daily[
        "expected_hours"
    ],
    errors="coerce",
)


cycling_daily[
    "observed_hours"
] = pd.to_numeric(
    cycling_daily[
        "observed_hours"
    ],
    errors="coerce",
)


cycling_daily[
    "coverage_ratio"
] = pd.to_numeric(
    cycling_daily[
        "coverage_ratio"
    ],
    errors="coerce",
)


cycling_daily[
    "daily_count"
] = pd.to_numeric(
    cycling_daily[
        "daily_count"
    ],
    errors="coerce",
)


# An active day is one where the counter was expected to report data.
cycling_daily[
    "is_active_day"
] = (
    cycling_daily[
        "expected_hours"
    ]
    .fillna(0)
    .gt(0)
)


# A usable day must be active, meet the coverage threshold,
# and have a daily count available.
cycling_daily[
    "is_usable_day"
] = (
    cycling_daily[
        "is_active_day"
    ]
    &
    cycling_daily[
        "coverage_ratio"
    ]
    .ge(
        DAILY_COVERAGE_THRESHOLD
    )
    &
    cycling_daily[
        "daily_count"
    ]
    .notna()
)


active_daily = (
    cycling_daily[
        cycling_daily[
            "is_active_day"
        ]
    ]
    .copy()
)


usable_daily = (
    cycling_daily[
        cycling_daily[
            "is_usable_day"
        ]
    ]
    .copy()
)


print(
    "Active counter-days:",
    f"{len(active_daily):,}",
)

print(
    "Usable counter-days:",
    f"{len(usable_daily):,}",
)

print(
    "Usable share of active days:",
    f"{len(usable_daily) / len(active_daily):.2%}"
    if len(active_daily) > 0
    else "N/A",
)


# Calculate quality statistics for each counter and year.
station_year_quality = (
    active_daily.groupby(
        [
            "station_id",
            "station_name",
            "district_name",
            "year",
        ],
        dropna=False,
    )
    .agg(
        expected_active_days=(
            "date",
            "nunique",
        ),

        usable_days=(
            "is_usable_day",
            "sum",
        ),

        observed_hours=(
            "observed_hours",
            "sum",
        ),

        expected_hours=(
            "expected_hours",
            "sum",
        ),
    )
    .reset_index()
)


station_year_quality[
    "usable_day_ratio"
] = (
    station_year_quality[
        "usable_days"
    ]
    /
    station_year_quality[
        "expected_active_days"
    ]
)


station_year_quality[
    "hourly_coverage_ratio"
] = (
    station_year_quality[
        "observed_hours"
    ]
    /
    station_year_quality[
        "expected_hours"
    ]
)


station_year_counts = (
    usable_daily.groupby(
        [
            "station_id",
            "year",
        ]
    )
    .agg(
        avg_daily_count=(
            "daily_count",
            "mean",
        ),

        median_daily_count=(
            "daily_count",
            "median",
        ),
    )
    .reset_index()
)


station_year_quality = (
    station_year_quality.merge(
        station_year_counts,
        on=[
            "station_id",
            "year",
        ],
        how="left",
        validate="one_to_one",
    )
)


station_year_quality.to_parquet(
    CYCLING_STATION_YEAR_QUALITY_PATH,
    index=False,
)


print(
    "\nStation-year quality records:",
    f"{len(station_year_quality):,}",
)


# Build the stable cycling counter panel.
section(
    "3. BUILDING STABLE CYCLING COUNTER PANEL"
)


panel_year_count = (
    PANEL_END_YEAR
    - PANEL_START_YEAR
    + 1
)


panel_quality = (
    station_year_quality[
        station_year_quality[
            "year"
        ]
        .between(
            PANEL_START_YEAR,
            PANEL_END_YEAR,
        )
    ]
    .copy()
)


eligible_panel_rows = (
    panel_quality[
        (
            panel_quality[
                "expected_active_days"
            ]
            >=
            MIN_EXPECTED_ACTIVE_DAYS
        )
        &
        (
            panel_quality[
                "usable_day_ratio"
            ]
            >=
            MIN_USABLE_DAY_RATIO
        )
    ]
    .copy()
)


eligible_year_counts = (
    eligible_panel_rows.groupby(
        "station_id"
    )
    [
        "year"
    ]
    .nunique()
)


stable_station_ids = (
    eligible_year_counts[
        eligible_year_counts
        ==
        panel_year_count
    ]
    .index
    .tolist()
)


print(
    "Panel period:",
    f"{PANEL_START_YEAR}–{PANEL_END_YEAR}",
)

print(
    "Required years:",
    panel_year_count,
)

print(
    "Stable panel counters:",
    len(
        stable_station_ids
    ),
)


# Stop here rather than weakening the panel criteria automatically.
if len(
    stable_station_ids
) == 0:

    print(
        "\nNo station passed the strict stable-panel criteria."
    )

    print(
        "Stations ranked by number of qualifying panel years:"
    )

    print(
        eligible_year_counts
        .sort_values(
            ascending=False
        )
        .head(20)
        .to_string()
    )

    raise ValueError(
        "\nNo stable cycling counter panel could be created.\n"
        "Do not lower thresholds automatically. "
        "Inspect the printed quality results first."
    )


stable_panel_stations = (
    station_year_quality[
        station_year_quality[
            "station_id"
        ]
        .isin(
            stable_station_ids
        )
    ]
    [
        [
            "station_id",
            "station_name",
            "district_name",
        ]
    ]
    .drop_duplicates()
    .sort_values(
        [
            "district_name",
            "station_id",
        ]
    )
)


stable_panel_stations.to_parquet(
    CYCLING_PANEL_STATIONS_PATH,
    index=False,
)


print(
    "\nStable panel station list:"
)

print(
    stable_panel_stations.to_string(
        index=False
    )
)


# Build the long-term cycling trend for the stable panel.
stable_daily = (
    usable_daily[
        usable_daily[
            "station_id"
        ]
        .isin(
            stable_station_ids
        )
        &
        usable_daily[
            "year"
        ]
        .between(
            PANEL_START_YEAR,
            PANEL_END_YEAR,
        )
    ]
    .copy()
)


# Calculate a yearly value for each counter before taking the
# city-wide average. This gives each counter equal weight.
stable_station_year = (
    stable_daily.groupby(
        [
            "year",
            "station_id",
            "station_name",
            "district_name",
        ],
        dropna=False,
    )
    .agg(
        avg_daily_count=(
            "daily_count",
            "mean",
        ),

        median_daily_count=(
            "daily_count",
            "median",
        ),

        usable_days=(
            "date",
            "nunique",
        ),
    )
    .reset_index()
)


cycling_panel_yearly = (
    stable_station_year.groupby(
        "year"
    )
    .agg(
        panel_station_count=(
            "station_id",
            "nunique",
        ),

        avg_daily_count_per_counter=(
            "avg_daily_count",
            "mean",
        ),

        median_daily_count_per_counter=(
            "avg_daily_count",
            "median",
        ),

        avg_usable_days=(
            "usable_days",
            "mean",
        ),
    )
    .reset_index()
)


baseline_rows = (
    cycling_panel_yearly[
        cycling_panel_yearly[
            "year"
        ]
        ==
        PANEL_START_YEAR
    ]
)


if baseline_rows.empty:

    raise ValueError(
        "Stable-panel baseline year is missing."
    )


baseline_value = (
    baseline_rows[
        "avg_daily_count_per_counter"
    ]
    .iloc[0]
)


cycling_panel_yearly[
    f"index_{PANEL_START_YEAR}_100"
] = (
    cycling_panel_yearly[
        "avg_daily_count_per_counter"
    ]
    /
    baseline_value
    *
    100
)


cycling_panel_yearly.to_parquet(
    CYCLING_PANEL_YEARLY_PATH,
    index=False,
)


print(
    "\nStable-panel yearly trend:"
)

print(
    cycling_panel_yearly.to_string(
        index=False
    )
)


# Recent cycling hourly profile
section(
    "4. RECENT CYCLING HOURLY PROFILE"
)


cycling_hourly[
    "count"
] = pd.to_numeric(
    cycling_hourly[
        "count"
    ],
    errors="coerce",
)


recent_hourly = (
    cycling_hourly[
        cycling_hourly[
            "year"
        ]
        .between(
            RECENT_PROFILE_START_YEAR,
            RECENT_PROFILE_END_YEAR,
        )
        &
        cycling_hourly[
            "count"
        ]
        .notna()
    ]
    .copy()
)


# Calculate each counter's hourly profile first and then average
# across counters so stations with more records do not get more weight.
station_hour_profile = (
    recent_hourly.groupby(
        [
            "station_id",
            "day_type",
            "hour",
        ],
        dropna=False,
    )
    .agg(
        station_avg_hourly_count=(
            "count",
            "mean",
        )
    )
    .reset_index()
)


cycling_hourly_profile = (
    station_hour_profile.groupby(
        [
            "day_type",
            "hour",
        ]
    )
    .agg(
        avg_count_per_counter=(
            "station_avg_hourly_count",
            "mean",
        ),

        median_count_per_counter=(
            "station_avg_hourly_count",
            "median",
        ),

        counter_count=(
            "station_id",
            "nunique",
        ),
    )
    .reset_index()
)


cycling_hourly_profile.to_parquet(
    CYCLING_HOURLY_PROFILE_PATH,
    index=False,
)


for day_type in [
    "Weekday",
    "Weekend",
]:

    subset = (
        cycling_hourly_profile[
            cycling_hourly_profile[
                "day_type"
            ]
            ==
            day_type
        ]
    )


    if subset.empty:
        continue


    peak = subset.loc[
        subset[
            "avg_count_per_counter"
        ]
        .idxmax()
    ]


    print(
        f"{day_type} peak hour: "
        f"{int(peak['hour']):02d}:00"
        f" | avg count/counter: "
        f"{peak['avg_count_per_counter']:.1f}"
    )


# Latest cycling district profile
section(
    "5. CYCLING BY DISTRICT"
)


latest_cycling_year = int(
    cycling_daily[
        "year"
    ]
    .max()
)


latest_cycling = (
    usable_daily[
        usable_daily[
            "year"
        ]
        ==
        latest_cycling_year
    ]
    .copy()
)


# Calculate station averages first so counters with more usable
# dates do not receive more weight in the district average.
station_latest_summary = (
    latest_cycling.groupby(
        [
            "station_id",
            "station_name",
            "district_name",
        ],
        dropna=False,
    )
    .agg(
        avg_daily_count=(
            "daily_count",
            "mean",
        ),

        median_daily_count=(
            "daily_count",
            "median",
        ),

        usable_days=(
            "date",
            "nunique",
        ),
    )
    .reset_index()
)


cycling_district_summary = (
    station_latest_summary.groupby(
        "district_name",
        dropna=False,
    )
    .agg(
        counter_count=(
            "station_id",
            "nunique",
        ),

        avg_daily_count_per_counter=(
            "avg_daily_count",
            "mean",
        ),

        median_daily_count_per_counter=(
            "avg_daily_count",
            "median",
        ),

        avg_usable_days=(
            "usable_days",
            "mean",
        ),
    )
    .reset_index()
)


cycling_district_summary[
    "year"
] = latest_cycling_year


cycling_district_summary.to_parquet(
    CYCLING_DISTRICT_PATH,
    index=False,
)


print(
    f"\nCycling district summary "
    f"({latest_cycling_year}):"
)


print(
    cycling_district_summary.sort_values(
        "avg_daily_count_per_counter",
        ascending=False,
    )
    .to_string(
        index=False
    )
)


# Active road disruption summary
section(
    "6. ACTIVE ROAD DISRUPTIONS"
)


active_roadworks = (
    roadworks[
        (
            roadworks[
                "event_status"
            ]
            ==
            "Active"
        )
        &
        roadworks[
            "district_name"
        ]
        .notna()
    ]
    .copy()
)


active_roadworks[
    "full_closure_flag"
] = (
    active_roadworks[
        "closure_category"
    ]
    ==
    "Full closure"
).astype(
    int
)


active_roadworks[
    "directional_closure_flag"
] = (
    active_roadworks[
        "closure_category"
    ]
    ==
    "Directional closure"
).astype(
    int
)


active_roadworks[
    "no_closure_flag"
] = (
    active_roadworks[
        "closure_category"
    ]
    ==
    "No closure"
).astype(
    int
)


roadworks_district_summary = (
    active_roadworks.groupby(
        "district_name"
    )
    .agg(
        active_disruptions=(
            "id",
            "nunique",
        ),

        full_closures=(
            "full_closure_flag",
            "sum",
        ),

        directional_closures=(
            "directional_closure_flag",
            "sum",
        ),

        no_closure_events=(
            "no_closure_flag",
            "sum",
        ),

        median_duration_days=(
            "duration_days",
            "median",
        ),

        avg_duration_days=(
            "duration_days",
            "mean",
        ),
    )
    .reset_index()
)


roadworks_district_summary.to_parquet(
    ROADWORKS_DISTRICT_PATH,
    index=False,
)


print(
    "\nActive Berlin disruptions:",
    len(
        active_roadworks
    ),
)


print(
    "\nRoad disruptions by district:"
)


print(
    roadworks_district_summary.sort_values(
        "active_disruptions",
        ascending=False,
    )
    .to_string(
        index=False
    )
)


# Public transport service analysis
section(
    "7. PUBLIC TRANSPORT SERVICE INTENSITY"
)


gtfs_service[
    "avg_scheduled_stop_departures"
] = pd.to_numeric(
    gtfs_service[
        "avg_scheduled_stop_departures"
    ],
    errors="coerce",
)


gtfs_route_service[
    "avg_scheduled_stop_departures"
] = pd.to_numeric(
    gtfs_route_service[
        "avg_scheduled_stop_departures"
    ],
    errors="coerce",
)


# Typical weekday service by district
weekday_daily_service = (
    gtfs_service[
        gtfs_service[
            "weekday"
        ]
        .isin(
            WEEKDAYS
        )
    ]
    .groupby(
        [
            "district_name",
            "weekday",
        ],
        dropna=False,
    )
    [
        "avg_scheduled_stop_departures"
    ]
    .sum()
    .reset_index()
)


weekday_district = (
    weekday_daily_service.groupby(
        "district_name",
        dropna=False,
    )
    [
        "avg_scheduled_stop_departures"
    ]
    .mean()
    .rename(
        "typical_weekday_service_intensity"
    )
    .reset_index()
)


# Typical weekend service by district
weekend_daily_service = (
    gtfs_service[
        gtfs_service[
            "weekday"
        ]
        .isin(
            WEEKENDS
        )
    ]
    .groupby(
        [
            "district_name",
            "weekday",
        ],
        dropna=False,
    )
    [
        "avg_scheduled_stop_departures"
    ]
    .sum()
    .reset_index()
)


weekend_district = (
    weekend_daily_service.groupby(
        "district_name",
        dropna=False,
    )
    [
        "avg_scheduled_stop_departures"
    ]
    .mean()
    .rename(
        "typical_weekend_service_intensity"
    )
    .reset_index()
)


# Stop-area counts by district
stop_area_counts = (
    gtfs_stations.groupby(
        "district_name",
        dropna=False,
    )
    [
        "station_id"
    ]
    .nunique()
    .rename(
        "stop_area_count"
    )
    .reset_index()
)


# Number of transport modes with scheduled service in each district
mode_diversity = (
    gtfs_service[
        gtfs_service[
            "avg_scheduled_stop_departures"
        ]
        >
        0
    ]
    .groupby(
        "district_name",
        dropna=False,
    )
    [
        "mode"
    ]
    .nunique()
    .rename(
        "transport_mode_count"
    )
    .reset_index()
)


# Routes serving each district
route_counts = (
    gtfs_route_service.groupby(
        "district_name",
        dropna=False,
    )
    [
        "route_id"
    ]
    .nunique()
    .rename(
        "route_count"
    )
    .reset_index()
)


# Combine public transport district statistics.
gtfs_district_summary = (
    stop_area_counts
    .merge(
        weekday_district,
        on="district_name",
        how="outer",
    )
    .merge(
        weekend_district,
        on="district_name",
        how="outer",
    )
    .merge(
        mode_diversity,
        on="district_name",
        how="outer",
    )
    .merge(
        route_counts,
        on="district_name",
        how="outer",
    )
)


gtfs_district_summary[
    "weekend_weekday_ratio"
] = (
    gtfs_district_summary[
        "typical_weekend_service_intensity"
    ]
    /
    gtfs_district_summary[
        "typical_weekday_service_intensity"
    ]
)


gtfs_district_summary.to_parquet(
    GTFS_DISTRICT_PATH,
    index=False,
)


print(
    "\nPublic transport by district:"
)


print(
    gtfs_district_summary.sort_values(
        "typical_weekday_service_intensity",
        ascending=False,
    )
    .to_string(
        index=False
    )
)


# Berlin-wide public transport hourly profile
gtfs_hourly_profile = (
    gtfs_service.groupby(
        [
            "weekday",
            "hour",
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


gtfs_hourly_profile.to_parquet(
    GTFS_HOURLY_PATH,
    index=False,
)


# Typical weekday public transport peak
weekday_transit_hour = (
    gtfs_service[
        gtfs_service[
            "weekday"
        ]
        .isin(
            WEEKDAYS
        )
    ]
    .groupby(
        [
            "weekday",
            "hour",
        ]
    )
    [
        "avg_scheduled_stop_departures"
    ]
    .sum()
    .reset_index()
)


typical_weekday_hour = (
    weekday_transit_hour.groupby(
        "hour"
    )
    [
        "avg_scheduled_stop_departures"
    ]
    .mean()
)


if not typical_weekday_hour.empty:

    transit_peak_hour = int(
        typical_weekday_hour
        .idxmax()
    )

    transit_peak_value = float(
        typical_weekday_hour
        .max()
    )

else:

    transit_peak_hour = None
    transit_peak_value = None


print(
    "\nTypical weekday transit peak:",
    (
        f"{transit_peak_hour:02d}:00 "
        f"| intensity: "
        f"{transit_peak_value:,.1f}"
        if transit_peak_hour is not None
        else "N/A"
    ),
)


# Combine cycling, roadworks and public transport by district.
section(
    "8. BUILDING CROSS-MODAL DISTRICT SUMMARY"
)


district_summary = (
    districts[
        [
            "district_code",
            "district_name",
        ]
    ]
    .drop_duplicates()
    .copy()
)


# Cycling fields
district_summary = (
    district_summary.merge(
        cycling_district_summary[
            [
                "district_name",
                "counter_count",
                "avg_daily_count_per_counter",
            ]
        ],
        on="district_name",
        how="left",
    )
)


# Road disruption fields
district_summary = (
    district_summary.merge(
        roadworks_district_summary[
            [
                "district_name",
                "active_disruptions",
                "full_closures",
            ]
        ],
        on="district_name",
        how="left",
    )
)


# Public transport fields
district_summary = (
    district_summary.merge(
        gtfs_district_summary[
            [
                "district_name",
                "stop_area_count",
                "route_count",
                "transport_mode_count",
                "typical_weekday_service_intensity",
                "typical_weekend_service_intensity",
                "weekend_weekday_ratio",
            ]
        ],
        on="district_name",
        how="left",
    )
)


count_columns = [
    "counter_count",
    "active_disruptions",
    "full_closures",
    "stop_area_count",
    "route_count",
    "transport_mode_count",
]


for column in count_columns:

    district_summary[
        column
    ] = (
        district_summary[
            column
        ]
        .fillna(0)
    )


district_summary.to_parquet(
    DISTRICT_MOBILITY_PATH,
    index=False,
)


print(
    district_summary.to_string(
        index=False
    )
)


# Extract a few values used in the dashboard summary.
section(
    "9. KEY EXPLORATORY FINDINGS"
)


# Long-term cycling change
first_year_row = (
    cycling_panel_yearly[
        cycling_panel_yearly[
            "year"
        ]
        ==
        PANEL_START_YEAR
    ]
)


last_year_row = (
    cycling_panel_yearly[
        cycling_panel_yearly[
            "year"
        ]
        ==
        PANEL_END_YEAR
    ]
)


cycling_change_pct = pd.NA


if (
    not first_year_row.empty
    and not last_year_row.empty
):

    first_value = float(
        first_year_row[
            "avg_daily_count_per_counter"
        ]
        .iloc[0]
    )

    last_value = float(
        last_year_row[
            "avg_daily_count_per_counter"
        ]
        .iloc[0]
    )

    cycling_change_pct = (
        (
            last_value
            / first_value
        )
        - 1
    ) * 100


print(
    "\nCYCLING"
)


print(
    "Stable-panel counters:",
    len(
        stable_station_ids
    ),
)


if pd.notna(
    cycling_change_pct
):

    print(
        f"Average daily cycling count per stable counter "
        f"changed by {cycling_change_pct:+.1f}% "
        f"between {PANEL_START_YEAR} "
        f"and {PANEL_END_YEAR}."
    )


# Cycling peak hours
weekday_cycling = (
    cycling_hourly_profile[
        cycling_hourly_profile[
            "day_type"
        ]
        ==
        "Weekday"
    ]
)


weekend_cycling = (
    cycling_hourly_profile[
        cycling_hourly_profile[
            "day_type"
        ]
        ==
        "Weekend"
    ]
)


weekday_cycling_peak_hour = None
weekend_cycling_peak_hour = None


if not weekday_cycling.empty:

    weekday_peak_row = weekday_cycling.loc[
        weekday_cycling[
            "avg_count_per_counter"
        ]
        .idxmax()
    ]

    weekday_cycling_peak_hour = int(
        weekday_peak_row[
            "hour"
        ]
    )


if not weekend_cycling.empty:

    weekend_peak_row = weekend_cycling.loc[
        weekend_cycling[
            "avg_count_per_counter"
        ]
        .idxmax()
    ]

    weekend_cycling_peak_hour = int(
        weekend_peak_row[
            "hour"
        ]
    )


# District with the most active road disruptions
top_roadworks_district = None
top_roadworks_count = None


if not roadworks_district_summary.empty:

    top_roadworks = (
        roadworks_district_summary
        .sort_values(
            "active_disruptions",
            ascending=False,
        )
        .iloc[0]
    )

    top_roadworks_district = (
        top_roadworks[
            "district_name"
        ]
    )

    top_roadworks_count = int(
        top_roadworks[
            "active_disruptions"
        ]
    )


    print(
        "\nROAD DISRUPTIONS"
    )

    print(
        f"{top_roadworks_district} "
        f"has the highest number of active "
        f"recorded disruptions: "
        f"{top_roadworks_count}."
    )


# District with the highest scheduled weekday service intensity
top_transit_district = None
top_transit_intensity = None


if not gtfs_district_summary.empty:

    top_transit = (
        gtfs_district_summary
        .sort_values(
            "typical_weekday_service_intensity",
            ascending=False,
        )
        .iloc[0]
    )


    top_transit_district = (
        top_transit[
            "district_name"
        ]
    )

    top_transit_intensity = float(
        top_transit[
            "typical_weekday_service_intensity"
        ]
    )


    print(
        "\nPUBLIC TRANSPORT"
    )

    print(
        f"{top_transit_district} "
        f"has the highest scheduled weekday "
        f"stop-departure intensity."
    )


# Build the KPI table loaded by the dashboard.
section(
    "10. PREPARING DASHBOARD KPI SUMMARY"
)


active_berlin_roadworks_count = int(
    len(
        active_roadworks
    )
)


active_full_closure_count = int(
    active_roadworks[
        "full_closure_flag"
    ]
    .sum()
)


median_active_roadwork_duration = (
    active_roadworks[
        "duration_days"
    ]
    .median()
)


kpi_records = [
    {
        "metric":
            "cycling_stable_panel_counters",

        "value":
            len(
                stable_station_ids
            ),

        "unit":
            "counters",
    },

    {
        "metric":
            "cycling_change_pct",

        "value":
            cycling_change_pct,

        "unit":
            "%",
    },

    {
        "metric":
            "cycling_latest_year",

        "value":
            latest_cycling_year,

        "unit":
            "year",
    },

    {
        "metric":
            "cycling_weekday_peak_hour",

        "value":
            weekday_cycling_peak_hour,

        "unit":
            "hour",
    },

    {
        "metric":
            "cycling_weekend_peak_hour",

        "value":
            weekend_cycling_peak_hour,

        "unit":
            "hour",
    },

    {
        "metric":
            "active_road_disruptions",

        "value":
            active_berlin_roadworks_count,

        "unit":
            "events",
    },

    {
        "metric":
            "active_full_closures",

        "value":
            active_full_closure_count,

        "unit":
            "events",
    },

    {
        "metric":
            "median_active_disruption_duration",

        "value":
            median_active_roadwork_duration,

        "unit":
            "days",
    },

    {
        "metric":
            "public_transport_stop_areas",

        "value":
            gtfs_stations[
                "station_id"
            ]
            .nunique(),

        "unit":
            "stop areas",
    },

    {
        "metric":
            "public_transport_routes",

        "value":
            gtfs_route_service[
                "route_id"
            ]
            .nunique(),

        "unit":
            "routes",
    },

    {
        "metric":
            "transit_weekday_peak_hour",

        "value":
            transit_peak_hour,

        "unit":
            "hour",
    },
]


kpi_summary = pd.DataFrame(
    kpi_records
)


kpi_summary.to_parquet(
    KPI_SUMMARY_PATH,
    index=False,
)


print(
    kpi_summary.to_string(
        index=False
    )
)


# Print the assumptions that matter when interpreting these tables.
section(
    "11. METHODOLOGY REMINDERS"
)


print(
    f"""
1. CYCLING LONG-TERM TREND
   Total counts across all cycling counters are NOT directly
   compared across 2012–2025 because the monitoring network
   expanded over time.

   The longitudinal trend uses a stable counter panel for
   {PANEL_START_YEAR}–{PANEL_END_YEAR}.

2. CYCLING DAILY QUALITY
   A counter-day is considered usable only when at least
   {DAILY_COVERAGE_THRESHOLD:.0%} of expected hourly records
   are available.

3. CYCLING MISSING VALUES
   Missing observations are never converted to zero.

4. ROAD DISRUPTIONS
   Roadworks represent a snapshot of recorded traffic
   disruptions. More disruptions do not automatically imply
   worse overall traffic conditions.

5. ROADWORK LOCATIONS
   District totals exclude records outside Berlin's district
   polygons.

6. GTFS STOP AREAS
   Stop-area counts are canonical public transport stop areas,
   not individual platform records.

7. GTFS SERVICE INTENSITY
   avg_scheduled_stop_departures measures scheduled stop
   departure intensity. It is NOT passenger volume and NOT
   a count of unique vehicles.

8. DISTRICT COMPARISONS
   Absolute district totals are influenced by district size,
   urban density, network structure and infrastructure supply.
"""
)


# List the analytical tables written by this script.
section(
    "ANALYTICS TABLES SAVED"
)


for path in sorted(
    ANALYTICS_DIR.glob(
        "*.parquet"
    )
):

    print(
        f"  {path}"
    )


print(
    "\nExploratory analysis completed successfully."
)