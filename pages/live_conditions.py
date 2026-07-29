"""
Current conditions page for the Berlin Mobility Dashboard.

Shows active and planned road disruptions across Berlin,
including their location, closure type and duration.
"""

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

from src.load_data import load_roadworks


STATUS_ORDER = [
    "Active",
    "Future",
    "Expired",
    "Unknown",
]

CLOSURE_ORDER = [
    "Full closure",
    "Directional closure",
    "No closure",
    "Unknown",
]

CLOSURE_COLORS = {
    "Full closure": [220, 53, 69, 210],
    "Directional closure": [245, 158, 11, 200],
    "No closure": [49, 130, 206, 175],
}


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


def format_date(value):
    """Format a timestamp for the map tooltip."""

    if value is None or pd.isna(value):
        return "Open-ended"

    return pd.Timestamp(value).strftime("%d %b %Y")


def event_color(closure_category):
    """Return the map marker colour for a closure category."""

    return CLOSURE_COLORS.get(
        closure_category,
        [120, 120, 120, 170],
    )


# Load data
roadworks = load_roadworks().copy()

for column in ["start_time", "end_time"]:
    if column in roadworks.columns:
        roadworks[column] = pd.to_datetime(
            roadworks[column],
            errors="coerce",
        )

for column in [
    "duration_days",
    "map_latitude",
    "map_longitude",
]:
    roadworks[column] = pd.to_numeric(
        roadworks[column],
        errors="coerce",
    )


# Keep only events assigned to a Berlin district.
# Two source records fall outside Berlin's district boundaries.
berlin_roadworks = roadworks[
    roadworks["district_name"].notna()
].copy()


# Header
st.title("Current Conditions")

st.markdown(
    "**Active and planned road disruptions across Berlin.**"
)

st.caption(
    "Berlin roadworks and closure data · "
    "Event status is derived from official validity periods"
)


# Filters
st.subheader("Filters")

filter_1, filter_2, filter_3, filter_4 = st.columns(
    [1.2, 1.4, 1.6, 1.6]
)

district_options = sorted(
    berlin_roadworks["district_name"]
    .dropna()
    .unique()
    .tolist()
)

available_statuses = [
    status
    for status in STATUS_ORDER
    if status
    in berlin_roadworks["event_status"].dropna().unique()
]

available_closures = [
    closure
    for closure in CLOSURE_ORDER
    if closure
    in berlin_roadworks["closure_category"].dropna().unique()
]

event_type_options = sorted(
    berlin_roadworks["event_type"]
    .dropna()
    .unique()
    .tolist()
)


with filter_1:
    selected_district = st.selectbox(
        "District",
        options=[
            "All Berlin",
            *district_options,
        ],
        index=0,
    )


with filter_2:
    selected_statuses = st.multiselect(
        "Event status",
        options=available_statuses,
        default=(
            ["Active"]
            if "Active" in available_statuses
            else available_statuses
        ),
    )


with filter_3:
    selected_closures = st.multiselect(
        "Closure type",
        options=available_closures,
        default=available_closures,
    )


with filter_4:
    selected_event_types = st.multiselect(
        "Event type",
        options=event_type_options,
        default=event_type_options,
    )


# Apply filters
filtered = berlin_roadworks.copy()

if selected_district != "All Berlin":
    filtered = filtered[
        filtered["district_name"] == selected_district
    ]

filtered = filtered[
    filtered["event_status"].isin(selected_statuses)
    & filtered["closure_category"].isin(selected_closures)
    & filtered["event_type"].isin(selected_event_types)
]


if filtered.empty:
    st.warning(
        "No road disruption events match the selected filters."
    )
    st.stop()


# Summary metrics
event_count = int(filtered["id"].nunique())

full_closures = int(
    filtered.loc[
        filtered["closure_category"] == "Full closure",
        "id",
    ].nunique()
)

directional_closures = int(
    filtered.loc[
        filtered["closure_category"] == "Directional closure",
        "id",
    ].nunique()
)

median_duration = filtered["duration_days"].median()


st.subheader("Road disruption summary")

k1, k2, k3, k4 = st.columns(4)


with k1:
    st.metric(
        "Visible disruptions",
        f"{event_count:,}",
        help=(
            "Number of unique disruption events "
            "matching the selected filters."
        ),
    )


with k2:
    st.metric(
        "Full closures",
        f"{full_closures:,}",
        help="Events classified as full road closures.",
    )


with k3:
    st.metric(
        "Directional closures",
        f"{directional_closures:,}",
        help=(
            "Events affecting an entire direction "
            "of travel."
        ),
    )


with k4:
    st.metric(
        "Median duration",
        (
            f"{median_duration:,.0f} days"
            if pd.notna(median_duration)
            else "—"
        ),
        help=(
            "Median planned duration for events "
            "with a known end time."
        ),
    )


st.divider()


# Map
st.subheader("Road disruptions on the map")

st.caption(
    "Marker colour shows the closure type. "
    "Hover over a marker for event details."
)

map_data = filtered.dropna(
    subset=[
        "map_latitude",
        "map_longitude",
    ]
).copy()

map_data["map_color"] = map_data[
    "closure_category"
].apply(event_color)

map_data["display_start"] = map_data[
    "start_time"
].apply(format_date)

map_data["display_end"] = map_data[
    "end_time"
].apply(format_date)

map_data["display_street"] = map_data[
    "street"
].fillna("Unknown street")

map_data["display_section"] = map_data[
    "section"
].fillna("")


if selected_district == "All Berlin":
    map_latitude = 52.52
    map_longitude = 13.405
    map_zoom = 9.6

else:
    map_latitude = map_data["map_latitude"].mean()
    map_longitude = map_data["map_longitude"].mean()
    map_zoom = 11.2


view_state = pdk.ViewState(
    latitude=map_latitude,
    longitude=map_longitude,
    zoom=map_zoom,
    pitch=0,
)

scatter_layer = pdk.Layer(
    "ScatterplotLayer",
    data=map_data,
    get_position=[
        "map_longitude",
        "map_latitude",
    ],
    get_fill_color="map_color",
    get_line_color=[255, 255, 255, 180],
    get_radius=90,
    radius_min_pixels=5,
    radius_max_pixels=13,
    line_width_min_pixels=1,
    pickable=True,
    stroked=True,
    filled=True,
)

tooltip = {
    "html": """
        <b>{display_street}</b><br/>
        {display_section}<br/><br/>

        <b>Type:</b> {event_type}<br/>
        <b>Closure:</b> {closure_category}<br/>
        <b>Status:</b> {event_status}<br/>
        <b>District:</b> {district_name}<br/><br/>

        <b>Start:</b> {display_start}<br/>
        <b>End:</b> {display_end}
    """,
    "style": {
        "backgroundColor": "rgba(30, 30, 30, 0.92)",
        "color": "white",
    },
}

deck = pdk.Deck(
    layers=[scatter_layer],
    initial_view_state=view_state,
    tooltip=tooltip,
    map_provider="carto",
    map_style="light",
)

st.pydeck_chart(
    deck,
    width="stretch",
    height=560,
)

st.markdown(
    """
    **Map legend:**  
    🔴 Full closure &nbsp;&nbsp;
    🟠 Directional closure &nbsp;&nbsp;
    🔵 No closure
    """
)


st.divider()


# District and closure summaries
left_chart, right_chart = st.columns(
    [1.25, 1],
    gap="large",
)


with left_chart:
    st.subheader("Disruptions by district")

    st.caption(
        "Number of events matching the current filters."
    )

    district_summary = (
        filtered
        .groupby(
            "district_name",
            as_index=False,
        )["id"]
        .nunique()
        .rename(
            columns={
                "id": "event_count",
            }
        )
        .sort_values(
            "event_count",
            ascending=True,
        )
    )

    district_fig = px.bar(
        district_summary,
        x="event_count",
        y="district_name",
        orientation="h",
        labels={
            "district_name": "",
            "event_count": "Disruptions",
        },
    )

    district_fig.update_traces(
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Disruptions: %{x}"
            "<extra></extra>"
        )
    )

    district_fig = clean_figure(district_fig)

    st.plotly_chart(
        district_fig,
        width="stretch",
    )


with right_chart:
    st.subheader("Events by closure type")

    st.caption(
        "Number of events in each closure category."
    )

    closure_summary = (
        filtered
        .groupby(
            "closure_category",
            as_index=False,
        )["id"]
        .nunique()
        .rename(
            columns={
                "id": "event_count",
            }
        )
    )

    closure_fig = px.bar(
        closure_summary,
        x="closure_category",
        y="event_count",
        labels={
            "closure_category": "",
            "event_count": "Events",
        },
    )

    closure_fig.update_traces(
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Events: %{y}"
            "<extra></extra>"
        )
    )

    closure_fig.update_xaxes(
        tickangle=-15,
    )

    closure_fig = clean_figure(closure_fig)

    st.plotly_chart(
        closure_fig,
        width="stretch",
    )


st.divider()


# Event table
st.subheader("Event details")

st.caption(
    "Road disruption records matching the current filters."
)

event_table = filtered[
    [
        "id",
        "district_name",
        "street",
        "section",
        "event_type",
        "closure_category",
        "event_status",
        "start_time",
        "end_time",
        "duration_days",
    ]
].copy()

event_table["duration_days"] = (
    event_table["duration_days"].round(0)
)

event_table = event_table.sort_values(
    [
        "district_name",
        "street",
    ]
)

event_table = event_table.rename(
    columns={
        "id": "Event ID",
        "district_name": "District",
        "street": "Street",
        "section": "Section",
        "event_type": "Event type",
        "closure_category": "Closure",
        "event_status": "Status",
        "start_time": "Start",
        "end_time": "End",
        "duration_days": "Duration (days)",
    }
)

st.dataframe(
    event_table,
    hide_index=True,
    width="stretch",
    column_config={
        "Start": st.column_config.DatetimeColumn(
            "Start",
            format="DD MMM YYYY HH:mm",
        ),
        "End": st.column_config.DatetimeColumn(
            "End",
            format="DD MMM YYYY HH:mm",
        ),
        "Duration (days)": st.column_config.NumberColumn(
            "Duration (days)",
            format="%.0f",
        ),
    },
)


# Notes
st.divider()

st.markdown(
    """
    <div class="note-box">
    <b>About the data</b><br>
    Road disruptions are recorded events, not direct measures of congestion
    or travel delay. Event status is calculated from the published start and
    end times. Two records outside Berlin's district boundaries are excluded
    from the figures on this page. Missing lane information remains missing
    rather than being treated as zero.
    </div>
    """,
    unsafe_allow_html=True,
)