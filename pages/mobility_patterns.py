"""
Mobility patterns page for the Berlin Mobility Dashboard.

Shows long-term cycling trends, hourly cycling activity
and scheduled public transport service across Berlin.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from src.load_data import (
    load_cycling_district_summary,
    load_cycling_hourly_profile,
    load_cycling_trend,
    load_gtfs_district_summary,
    load_gtfs_hourly_profile,
)


WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
]

WEEKEND_DAYS = [
    "Saturday",
    "Sunday",
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
        font-size: 2.5rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.03em;
    }

    h2 {
        font-size: 1.5rem !important;
        margin-top: 1.4rem !important;
    }

    h3 {
        font-size: 1.15rem !important;
    }

    div[data-testid="stMetric"] {
        background-color: rgba(128, 128, 128, 0.06);
        border: 1px solid rgba(128, 128, 128, 0.16);
        padding: 1rem 1.1rem;
        border-radius: 12px;
    }

    .note-box {
        background-color: rgba(128, 128, 128, 0.05);
        border-left: 3px solid #777;
        border-radius: 0 8px 8px 0;
        padding: 0.8rem 1rem;
        font-size: 0.9rem;
        line-height: 1.5;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def clean_figure(fig, top_margin=35):
    """Apply the common Plotly layout used on this page."""

    fig.update_layout(
        template="plotly_white",
        margin=dict(l=10, r=10, t=top_margin, b=10),
        legend_title_text="",
        hoverlabel=dict(font_size=13),
        font=dict(size=12),
    )

    return fig


def format_hour(hour):
    """Convert an integer hour to HH:00."""

    if hour is None or pd.isna(hour):
        return "—"

    return f"{int(hour):02d}:00"


# Load data
cycling_trend = load_cycling_trend()
cycling_hourly = load_cycling_hourly_profile()
cycling_district = load_cycling_district_summary()
gtfs_hourly = load_gtfs_hourly_profile()
gtfs_district = load_gtfs_district_summary()


# Header
st.title("Mobility Patterns")

st.markdown(
    "**Cycling activity over time and scheduled public transport "
    "service across Berlin.**"
)

st.caption(
    "Cycling: validated counter data · "
    "Public transport: VBB GTFS schedules"
)


cycling_tab, transit_tab = st.tabs(
    [
        "🚲 Cycling",
        "🚇 Public Transport",
    ]
)


# Cycling
with cycling_tab:

    # Summary metrics
    first_year = cycling_trend["year"].min()
    last_year = cycling_trend["year"].max()

    first_index = cycling_trend.loc[
        cycling_trend["year"] == first_year,
        "index_2017_100",
    ].iloc[0]

    last_index = cycling_trend.loc[
        cycling_trend["year"] == last_year,
        "index_2017_100",
    ].iloc[0]

    cycling_change = last_index - first_index
    panel_counter_count = int(cycling_trend["panel_station_count"].max())

    weekday_profile = cycling_hourly[
        cycling_hourly["day_type"] == "Weekday"
    ]

    weekend_profile = cycling_hourly[
        cycling_hourly["day_type"] == "Weekend"
    ]

    weekday_peak_hour = (
        int(
            weekday_profile.loc[
                weekday_profile["avg_count_per_counter"].idxmax(),
                "hour",
            ]
        )
        if not weekday_profile.empty
        else None
    )

    weekend_peak_hour = (
        int(
            weekend_profile.loc[
                weekend_profile["avg_count_per_counter"].idxmax(),
                "hour",
            ]
        )
        if not weekend_profile.empty
        else None
    )

    st.subheader("Cycling summary")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "2017–2025 change",
            f"{cycling_change:+.1f}%",
            help=(
                "Change in the cycling index for the stable "
                "counter panel between 2017 and 2025."
            ),
        )

    with c2:
        st.metric(
            "Stable counters",
            f"{panel_counter_count}",
            help=(
                "Counters included throughout the "
                "2017–2025 comparison."
            ),
        )

    with c3:
        st.metric(
            "Weekday peak",
            format_hour(weekday_peak_hour),
        )

    with c4:
        st.metric(
            "Weekend peak",
            format_hour(weekend_peak_hour),
        )

    st.divider()

    # Long-term trend
    st.subheader("Long-term cycling trend")

    st.caption(
        "The index uses the same 24 counters from 2017 to 2025. "
        "2017 = 100."
    )

    cycling_trend_fig = px.line(
        cycling_trend,
        x="year",
        y="index_2017_100",
        markers=True,
        labels={
            "year": "",
            "index_2017_100": "Cycling index (2017 = 100)",
        },
    )

    cycling_trend_fig.update_traces(
        line_width=3,
        marker_size=8,
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Cycling index: %{y:.1f}"
            "<extra></extra>"
        ),
    )

    cycling_trend_fig.add_hline(
        y=100,
        line_dash="dot",
        annotation_text="2017 baseline",
        annotation_position="bottom right",
    )

    cycling_trend_fig.update_xaxes(
        dtick=1,
        showgrid=False,
    )

    cycling_trend_fig.update_yaxes(
        range=[95, 130],
        dtick=5,
    )

    cycling_trend_fig = clean_figure(cycling_trend_fig)

    st.plotly_chart(
        cycling_trend_fig,
        width="stretch",
    )

    st.markdown(
        """
        <div class="note-box">
        Berlin added cycling counters over time. However, 
        I used the same 24 counters to make the yearly comparison more consistent. 
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    # Hourly cycling activity
    st.subheader("Cycling by hour")

    st.caption(
        "Average hourly activity per counter on weekdays and weekends, "
        "based on observations from 2023 to 2025."
    )

    selected_day_types = st.multiselect(
        "Compare day types",
        options=[
            "Weekday",
            "Weekend",
        ],
        default=[
            "Weekday",
            "Weekend",
        ],
        key="cycling_day_types",
    )

    filtered_cycling_hourly = cycling_hourly[
        cycling_hourly["day_type"].isin(selected_day_types)
    ].copy()

    if filtered_cycling_hourly.empty:
        st.info("Select at least one day type.")

    else:
        cycling_hourly_fig = px.line(
            filtered_cycling_hourly,
            x="hour",
            y="avg_count_per_counter",
            color="day_type",
            markers=True,
            labels={
                "hour": "Hour",
                "avg_count_per_counter": "Average hourly count per counter",
                "day_type": "Day type",
            },
        )

        cycling_hourly_fig.update_traces(
            line_width=2.5,
            marker_size=6,
            hovertemplate=(
                "<b>%{fullData.name}</b><br>"
                "%{x}:00<br>"
                "Average count per counter: %{y:.1f}"
                "<extra></extra>"
            ),
        )

        cycling_hourly_fig.update_xaxes(
            tickmode="array",
            tickvals=list(range(0, 24, 2)),
            ticktext=[
                f"{hour:02d}:00"
                for hour in range(0, 24, 2)
            ],
            showgrid=False,
        )

        cycling_hourly_fig = clean_figure(cycling_hourly_fig)

        st.plotly_chart(
            cycling_hourly_fig,
            width="stretch",
        )

    peak_left, peak_right = st.columns(2)

    with peak_left:
        st.info(
            f"**Weekday peak:** {format_hour(weekday_peak_hour)}."
        )

    with peak_right:
        st.info(
            f"**Weekend peak:** {format_hour(weekend_peak_hour)}."
        )

    st.divider()

    # District comparison
    st.subheader("Monitored cycling activity by district")

    latest_year = int(cycling_district["year"].max())

    st.caption(
        f"Average daily activity per monitored counter in {latest_year}. "
        "The number of counters differs by district."
    )

    cycling_district_plot = (
        cycling_district.loc[
            cycling_district["year"] == latest_year,
            [
                "district_name",
                "counter_count",
                "avg_daily_count_per_counter",
            ],
        ]
        .sort_values(
            "avg_daily_count_per_counter",
            ascending=True,
        )
        .copy()
    )

    cycling_district_fig = px.bar(
        cycling_district_plot,
        x="avg_daily_count_per_counter",
        y="district_name",
        orientation="h",
        custom_data=["counter_count"],
        labels={
            "district_name": "",
            "avg_daily_count_per_counter": "Average daily count per counter",
        },
    )

    cycling_district_fig.update_traces(
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Average daily count per counter: %{x:,.0f}<br>"
            "Counters: %{customdata[0]}"
            "<extra></extra>"
        )
    )

    cycling_district_fig = clean_figure(cycling_district_fig)

    st.plotly_chart(
        cycling_district_fig,
        width="stretch",
    )

    st.warning(
        "These values describe activity at monitored counters, "
        "not total cycling across each district. Some districts have "
        "only one counter, while others have several."
    )


# Public transport
with transit_tab:

    mode_list = sorted(
        gtfs_hourly["mode"]
        .dropna()
        .unique()
        .tolist()
    )

    district_count = gtfs_district["district_name"].nunique()
    total_stop_areas = int(gtfs_district["stop_area_count"].sum())

    weekday_total = (
        gtfs_hourly[
            gtfs_hourly["weekday"].isin(WEEKDAYS)
        ]
        .groupby(
            ["weekday", "hour"],
            as_index=False,
        )["avg_scheduled_stop_departures"]
        .sum()
    )

    typical_weekday_hour = (
        weekday_total
        .groupby(
            "hour",
            as_index=False,
        )["avg_scheduled_stop_departures"]
        .mean()
    )

    transit_peak_hour = (
        int(
            typical_weekday_hour.loc[
                typical_weekday_hour[
                    "avg_scheduled_stop_departures"
                ].idxmax(),
                "hour",
            ]
        )
        if not typical_weekday_hour.empty
        else None
    )

    st.subheader("Public transport summary")

    t1, t2, t3, t4 = st.columns(4)

    with t1:
        st.metric(
            "Stop areas",
            f"{total_stop_areas:,}",
        )

    with t2:
        st.metric(
            "Transport modes",
            f"{len(mode_list)}",
        )

    with t3:
        st.metric(
            "Berlin districts",
            f"{district_count}",
        )

    with t4:
        st.metric(
            "Weekday peak",
            format_hour(transit_peak_hour),
        )

    st.divider()

    # Hourly service
    st.subheader("Scheduled service by hour")

    st.caption(
        "Average scheduled stop departures by transport mode and day."
    )

    filter_col_1, filter_col_2 = st.columns([1, 2])

    with filter_col_1:
        selected_day = st.selectbox(
            "Day",
            options=[
                "Typical weekday",
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
                "Typical weekend",
            ],
            index=0,
        )

    with filter_col_2:
        selected_modes = st.multiselect(
            "Transport modes",
            options=mode_list,
            default=mode_list,
        )

    if selected_day == "Typical weekday":
        selected_days = WEEKDAYS

    elif selected_day == "Typical weekend":
        selected_days = WEEKEND_DAYS

    else:
        selected_days = [selected_day]

    transit_filtered = gtfs_hourly[
        gtfs_hourly["weekday"].isin(selected_days)
        & gtfs_hourly["mode"].isin(selected_modes)
    ].copy()

    transit_mode_hour = (
        transit_filtered
        .groupby(
            ["weekday", "hour", "mode"],
            as_index=False,
        )["avg_scheduled_stop_departures"]
        .sum()
        .groupby(
            ["hour", "mode"],
            as_index=False,
        )["avg_scheduled_stop_departures"]
        .mean()
    )

    if transit_mode_hour.empty:
        st.info("Select at least one transport mode.")

    else:
        transit_hour_fig = px.line(
            transit_mode_hour,
            x="hour",
            y="avg_scheduled_stop_departures",
            color="mode",
            labels={
                "hour": "Hour",
                "avg_scheduled_stop_departures": "Service intensity",
                "mode": "Mode",
            },
        )

        transit_hour_fig.update_traces(
            line_width=2.5,
            hovertemplate=(
                "<b>%{fullData.name}</b><br>"
                "%{x}:00<br>"
                "Service intensity: %{y:,.0f}"
                "<extra></extra>"
            ),
        )

        transit_hour_fig.update_xaxes(
            tickmode="array",
            tickvals=list(range(0, 24, 2)),
            ticktext=[
                f"{hour:02d}:00"
                for hour in range(0, 24, 2)
            ],
            showgrid=False,
        )

        transit_hour_fig = clean_figure(transit_hour_fig)

        st.plotly_chart(
            transit_hour_fig,
            width="stretch",
        )

    st.markdown(
        """
        <div class="note-box">
        <b>What does service intensity mean?</b><br>
        It is based on average scheduled stop departures.
        It does not measure passenger numbers or unique vehicles.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    # District service comparison
    st.subheader("Weekday and weekend service by district")

    st.caption(
        "Scheduled service intensity for each Berlin district."
    )

    district_service_long = (
        gtfs_district[
            [
                "district_name",
                "typical_weekday_service_intensity",
                "typical_weekend_service_intensity",
            ]
        ]
        .rename(
            columns={
                "typical_weekday_service_intensity": "Weekday",
                "typical_weekend_service_intensity": "Weekend",
            }
        )
        .melt(
            id_vars="district_name",
            var_name="Day type",
            value_name="Service intensity",
        )
    )

    district_order = (
        gtfs_district
        .sort_values(
            "typical_weekday_service_intensity",
            ascending=False,
        )["district_name"]
        .tolist()
    )

    district_service_fig = px.bar(
        district_service_long,
        x="district_name",
        y="Service intensity",
        color="Day type",
        barmode="group",
        category_orders={
            "district_name": district_order,
        },
        labels={
            "district_name": "District",
        },
    )

    district_service_fig.update_xaxes(
        tickangle=-35,
    )

    district_service_fig.update_traces(
        hovertemplate=(
            "<b>%{x}</b><br>"
            "%{fullData.name}: %{y:,.0f}"
            "<extra></extra>"
        )
    )

    district_service_fig = clean_figure(
        district_service_fig,
        top_margin=45,
    )

    st.plotly_chart(
        district_service_fig,
        width="stretch",
    )

    # Weekend comparison
    st.subheader("Weekend service compared with weekdays")

    st.caption(
        "Weekend scheduled service as a percentage "
        "of the typical weekday level."
    )

    weekend_ratio = gtfs_district[
        [
            "district_name",
            "weekend_weekday_ratio",
        ]
    ].copy()

    weekend_ratio["weekend_share_pct"] = (
        weekend_ratio["weekend_weekday_ratio"] * 100
    )

    weekend_ratio = weekend_ratio.sort_values(
        "weekend_share_pct",
        ascending=True,
    )

    weekend_ratio_fig = px.bar(
        weekend_ratio,
        x="weekend_share_pct",
        y="district_name",
        orientation="h",
        labels={
            "district_name": "",
            "weekend_share_pct": "Weekend service (% of weekday)",
        },
    )

    weekend_ratio_fig.update_traces(
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Weekend / weekday: %{x:.1f}%"
            "<extra></extra>"
        )
    )

    weekend_ratio_fig = clean_figure(weekend_ratio_fig)

    st.plotly_chart(
        weekend_ratio_fig,
        width="stretch",
    )

    st.caption(
        "A value of 80% means weekend scheduled service "
        "is 80% of the typical weekday level."
    )


# Notes
st.divider()

st.caption(
    """
    **About the metrics:** The long-term cycling trend uses the same
    24 counters from 2017 to 2025. District cycling figures describe
    monitored counters only. Public transport figures are based on
    scheduled VBB GTFS service and do not represent passenger numbers.
    """
)