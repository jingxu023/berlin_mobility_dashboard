"""
Overview page for the Berlin Mobility Dashboard.

Summarizes cycling trends, current road disruptions
and scheduled public transport service across Berlin.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from src.load_data import (
    load_cycling_trend,
    load_dashboard_kpis,
    load_gtfs_hourly_profile,
    load_roadworks_district_summary,
)


WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
]


# Page styling
st.markdown(
    """
    <style>
    .block-container {
        max-width: 1400px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    h1 {
        font-size: 2.6rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.03em;
    }

    h2 {
        font-size: 1.45rem !important;
        margin-top: 1.5rem !important;
    }

    div[data-testid="stMetric"] {
        background-color: rgba(128, 128, 128, 0.06);
        border: 1px solid rgba(128, 128, 128, 0.16);
        padding: 1rem 1.1rem;
        border-radius: 12px;
    }

    div[data-testid="stMetricLabel"] {
        font-size: 0.9rem;
    }

    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
    }

    .insight-box {
        border-left: 3px solid #777;
        padding: 0.8rem 1rem;
        margin-bottom: 0.8rem;
        background-color: rgba(128, 128, 128, 0.05);
        border-radius: 0 8px 8px 0;
        min-height: 115px;
    }

    .insight-title {
        font-weight: 650;
        margin-bottom: 0.35rem;
    }

    .insight-text {
        font-size: 0.92rem;
        line-height: 1.5;
        opacity: 0.85;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_kpi(kpi_df: pd.DataFrame, metric_name: str):
    """Return one value from the dashboard KPI table."""

    result = kpi_df.loc[
        kpi_df["metric"] == metric_name,
        "value",
    ]

    if result.empty:
        return None

    value = result.iloc[0]

    if pd.isna(value):
        return None

    return value


def format_signed_percent(value):
    """Format a percentage with an explicit sign."""

    if value is None:
        return "—"

    return f"{value:+.1f}%"


def clean_plotly_figure(fig):
    """Apply the common Plotly layout used on this page."""

    fig.update_layout(
        template="plotly_white",
        margin=dict(l=10, r=10, t=35, b=10),
        legend_title_text="",
        hoverlabel=dict(font_size=13),
        font=dict(size=12),
    )

    return fig


# Load data
kpis = load_dashboard_kpis()
cycling_trend = load_cycling_trend()
roadworks_summary = load_roadworks_district_summary()
gtfs_hourly = load_gtfs_hourly_profile()


# Header
st.title("Berlin Mobility Dashboard")

st.markdown(
    "**Cycling activity, road disruptions and public transport "
    "service across Berlin.**"
)

st.caption(
    "Berlin open data and VBB GTFS · "
    "Cycling data: 2012–2025 · VBB schedule: 2026"
)


# Summary metrics
cycling_change = get_kpi(kpis, "cycling_change_pct")
cycling_peak = get_kpi(kpis, "cycling_weekday_peak_hour")
active_roadworks = get_kpi(kpis, "active_road_disruptions")
stop_areas = get_kpi(kpis, "public_transport_stop_areas")

st.subheader("Mobility snapshot")

kpi_1, kpi_2, kpi_3, kpi_4 = st.columns(4)

with kpi_1:
    st.metric(
        label="Cycling activity change",
        value=format_signed_percent(cycling_change),
        help=(
            "Change in average daily cycling activity per stable "
            "counter between 2017 and 2025."
        ),
    )

    st.caption("24 stable counters, 2017–2025")


with kpi_2:
    st.metric(
        label="Weekday cycling peak",
        value=(
            f"{int(cycling_peak):02d}:00"
            if cycling_peak is not None
            else "—"
        ),
        help="Peak hour in the recent weekday cycling profile.",
    )

    st.caption("Based on 2023–2025 observations")


with kpi_3:
    st.metric(
        label="Active road disruptions",
        value=(
            f"{int(active_roadworks):,}"
            if active_roadworks is not None
            else "—"
        ),
        help=(
            "Road disruption events classified as active "
            "in the processed snapshot."
        ),
    )

    st.caption("Current roadworks snapshot")


with kpi_4:
    st.metric(
        label="Public transport stop areas",
        value=(
            f"{int(stop_areas):,}"
            if stop_areas is not None
            else "—"
        ),
        help=(
            "Canonical public transport stop areas derived "
            "from the VBB GTFS feed."
        ),
    )

    st.caption(
        "Bus · Tram · U-Bahn · S-Bahn · Regional Rail · Ferry"
    )


st.divider()


# Cycling trend
st.subheader("Cycling activity remains above its 2017 baseline")

st.caption(
    "Average daily cycling activity using the same "
    "24 counters from 2017 to 2025."
)

cycling_fig = px.line(
    cycling_trend,
    x="year",
    y="index_2017_100",
    markers=True,
    labels={
        "year": "",
        "index_2017_100": "Cycling index (2017 = 100)",
    },
)

cycling_fig.update_traces(
    line_width=3,
    marker_size=8,
    hovertemplate=(
        "<b>%{x}</b><br>"
        "Cycling index: %{y:.1f}"
        "<extra></extra>"
    ),
)

cycling_fig.add_hline(
    y=100,
    line_dash="dot",
    annotation_text="2017 baseline",
    annotation_position="bottom right",
)

cycling_fig.update_xaxes(
    dtick=1,
    showgrid=False,
)

cycling_fig.update_yaxes(
    range=[95, 130],
    dtick=5,
)

cycling_fig = clean_plotly_figure(cycling_fig)

st.plotly_chart(
    cycling_fig,
    width="stretch",
)

st.caption(
    "The same 24 counters are used every year from 2017 to 2025. "
    "Changes in the size of the monitoring network therefore do not "
    "affect this comparison."
)


st.divider()


# Road disruptions and public transport
left_column, right_column = st.columns(
    2,
    gap="large",
)


with left_column:
    st.subheader("Active road disruptions by district")

    st.caption(
        "Number of active recorded events in each Berlin district."
    )

    roadworks_chart_data = (
        roadworks_summary[
            [
                "district_name",
                "active_disruptions",
            ]
        ]
        .sort_values(
            "active_disruptions",
            ascending=True,
        )
    )

    roadworks_fig = px.bar(
        roadworks_chart_data,
        x="active_disruptions",
        y="district_name",
        orientation="h",
        labels={
            "district_name": "",
            "active_disruptions": "Active disruptions",
        },
    )

    roadworks_fig.update_layout(
        yaxis=dict(categoryorder="total ascending")
    )

    roadworks_fig.update_traces(
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Active disruptions: %{x}"
            "<extra></extra>"
        )
    )

    roadworks_fig = clean_plotly_figure(roadworks_fig)

    st.plotly_chart(
        roadworks_fig,
        width="stretch",
    )


with right_column:
    st.subheader("Scheduled public transport by hour")

    st.caption(
        "Typical weekday service based on scheduled stop departures."
    )

    weekday_gtfs = (
        gtfs_hourly[
            gtfs_hourly["weekday"].isin(WEEKDAYS)
        ]
        .groupby(
            ["weekday", "hour"],
            as_index=False,
        )["avg_scheduled_stop_departures"]
        .sum()
    )

    typical_weekday_gtfs = (
        weekday_gtfs
        .groupby(
            "hour",
            as_index=False,
        )["avg_scheduled_stop_departures"]
        .mean()
    )

    transit_fig = px.area(
        typical_weekday_gtfs,
        x="hour",
        y="avg_scheduled_stop_departures",
        labels={
            "hour": "Hour",
            "avg_scheduled_stop_departures": "Service intensity",
        },
    )

    transit_fig.update_xaxes(
        tickmode="array",
        tickvals=list(range(0, 24, 3)),
        ticktext=[
            f"{hour:02d}:00"
            for hour in range(0, 24, 3)
        ],
        showgrid=False,
    )

    transit_fig.update_traces(
        hovertemplate=(
            "<b>%{x}:00</b><br>"
            "Service intensity: %{y:,.0f}"
            "<extra></extra>"
        )
    )

    transit_fig = clean_plotly_figure(transit_fig)

    st.plotly_chart(
        transit_fig,
        width="stretch",
    )


st.divider()


# Key observations
st.subheader("Key observations")

insight_1, insight_2, insight_3 = st.columns(3)


with insight_1:
    st.markdown(
        """
        <div class="insight-box">
            <div class="insight-title">
                🚲 Cycling peaks later on weekdays
            </div>
            <div class="insight-text">
                The weekday peak is around 18:00.
                On weekends, the peak is around 14:00.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with insight_2:
    st.markdown(
        """
        <div class="insight-box">
            <div class="insight-title">
                🚧 Mitte has the most active disruptions
            </div>
            <div class="insight-text">
                The current snapshot records more active road
                disruption events in Mitte than in any other district.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with insight_3:
    st.markdown(
        """
        <div class="insight-box">
            <div class="insight-title">
                🚇 Scheduled service peaks around 07:00
            </div>
            <div class="insight-text">
                On a typical weekday, scheduled public transport
                service is highest around 07:00.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# Notes
st.divider()

st.caption(
    """
    **About the metrics:** The cycling trend uses the same 24 counters
    from 2017 to 2025. Road disruption figures refer to recorded events
    in the current snapshot and are not a measure of congestion.
    Public transport figures come from scheduled GTFS service and do not
    represent passenger numbers.
    """
)