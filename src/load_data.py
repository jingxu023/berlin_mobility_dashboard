"""
Load processed datasets used by the Berlin Mobility Dashboard.

Provides cached access to analytics tables, road disruption records,
district boundaries, cycling trends, and public transport summaries.
"""

from pathlib import Path
import json

import pandas as pd
import streamlit as st


# =========================================================
# Project paths
# =========================================================

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


# =========================================================
# Helper
# =========================================================

def _check_file(path: Path) -> Path:
    """
    Validate that a required dashboard data file exists.
    """

    if not path.exists():
        raise FileNotFoundError(
            f"Required dashboard data file not found:\n{path}"
        )

    return path


# =========================================================
# Berlin district boundaries
# =========================================================

@st.cache_data
def load_district_geojson():
    """
    Load Berlin district boundaries as a GeoJSON dictionary.
    """

    path = _check_file(
        PROCESSED_DIR
        / "berlin_bezirke.geojson"
    )

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


# =========================================================
# Dashboard KPIs
# =========================================================

@st.cache_data
def load_dashboard_kpis():
    """
    Load precomputed dashboard KPI values.
    """

    path = _check_file(
        ANALYTICS_DIR
        / "dashboard_kpi_summary.parquet"
    )

    return pd.read_parquet(path)


# =========================================================
# Cross-modal district summary
# =========================================================

@st.cache_data
def load_district_mobility_summary():
    """
    Load district-level cycling, roadwork, and transit indicators.
    """

    path = _check_file(
        ANALYTICS_DIR
        / "district_mobility_summary.parquet"
    )

    return pd.read_parquet(path)


# =========================================================
# Cycling analytics
# =========================================================

@st.cache_data
def load_cycling_trend():
    """
    Load the stable-panel cycling trend for 2017–2025.
    """

    path = _check_file(
        ANALYTICS_DIR
        / "cycling_stable_panel_yearly.parquet"
    )

    return pd.read_parquet(path)


@st.cache_data
def load_cycling_hourly_profile():
    """
    Load recent weekday/weekend cycling hourly profiles.
    """

    path = _check_file(
        ANALYTICS_DIR
        / "cycling_recent_hourly_profile.parquet"
    )

    return pd.read_parquet(path)


@st.cache_data
def load_cycling_district_summary():
    """
    Load latest-year cycling counter summaries by district.
    """

    path = _check_file(
        ANALYTICS_DIR
        / "cycling_district_summary.parquet"
    )

    return pd.read_parquet(path)


@st.cache_data
def load_cycling_panel_stations():
    """
    Load cycling counters included in the stable longitudinal panel.
    """

    path = _check_file(
        ANALYTICS_DIR
        / "cycling_stable_panel_stations.parquet"
    )

    return pd.read_parquet(path)


# =========================================================
# Road disruption analytics
# =========================================================

@st.cache_data
def load_roadworks():
    """
    Load processed road disruption event records.
    """

    path = _check_file(
        PROCESSED_DIR
        / "roadworks.parquet"
    )

    return pd.read_parquet(path)


@st.cache_data
def load_roadworks_district_summary():
    """
    Load active road disruption statistics by district.
    """

    path = _check_file(
        ANALYTICS_DIR
        / "roadworks_district_summary.parquet"
    )

    return pd.read_parquet(path)


@st.cache_data
def load_roadworks_map_geojson():
    """
    Load representative road disruption map points.
    """

    path = _check_file(
        PROCESSED_DIR
        / "roadworks_map_points.geojson"
    )

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


# =========================================================
# Public transport analytics
# =========================================================

@st.cache_data
def load_gtfs_district_summary():
    """
    Load district-level public transport supply indicators.
    """

    path = _check_file(
        ANALYTICS_DIR
        / "gtfs_district_summary.parquet"
    )

    return pd.read_parquet(path)


@st.cache_data
def load_gtfs_hourly_profile():
    """
    Load scheduled public transport service intensity by hour and mode.
    """

    path = _check_file(
        ANALYTICS_DIR
        / "gtfs_hourly_profile.parquet"
    )

    return pd.read_parquet(path)


@st.cache_data
def load_gtfs_stations():
    """
    Load canonical Berlin public transport stop areas.
    """

    path = _check_file(
        PROCESSED_DIR
        / "gtfs_berlin_stations.parquet"
    )

    return pd.read_parquet(path)


@st.cache_data
def load_gtfs_routes():
    """
    Load public transport routes serving Berlin.
    """

    path = _check_file(
        PROCESSED_DIR
        / "gtfs_berlin_routes.parquet"
    )

    return pd.read_parquet(path)