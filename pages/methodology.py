"""
Methodology page for the Berlin Mobility Dashboard.

Documents the source data, processing steps, metric definitions,
data-quality decisions and limitations of the analysis.
"""

import pandas as pd
import streamlit as st

from src.load_data import load_dashboard_kpis


# Page styling
st.markdown(
    """
    <style>
    .block-container {
        max-width: 1250px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    h1 {
        font-size: 2.5rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.03em;
    }

    h2 {
        font-size: 1.5rem !important;
        margin-top: 1.6rem !important;
    }

    h3 {
        font-size: 1.15rem !important;
    }

    .source-card {
        background-color: rgba(128, 128, 128, 0.05);
        border: 1px solid rgba(128, 128, 128, 0.14);
        border-radius: 12px;
        padding: 1rem 1.1rem;
        min-height: 165px;
    }

    .source-title {
        font-size: 1rem;
        font-weight: 650;
        margin-bottom: 0.4rem;
    }

    .source-text {
        font-size: 0.9rem;
        line-height: 1.5;
        opacity: 0.85;
    }

    .pipeline-step {
        background-color: rgba(128, 128, 128, 0.05);
        border: 1px solid rgba(128, 128, 128, 0.14);
        border-radius: 10px;
        padding: 0.8rem 0.9rem;
        text-align: center;
        min-height: 95px;
    }

    .pipeline-number {
        font-size: 0.75rem;
        opacity: 0.55;
        margin-bottom: 0.2rem;
    }

    .pipeline-title {
        font-size: 0.95rem;
        font-weight: 650;
        margin-bottom: 0.2rem;
    }

    .pipeline-text {
        font-size: 0.78rem;
        opacity: 0.7;
        line-height: 1.35;
    }

    .note-box {
        background-color: rgba(128, 128, 128, 0.05);
        border-left: 3px solid #777;
        border-radius: 0 8px 8px 0;
        padding: 0.85rem 1rem;
        margin-bottom: 0.8rem;
        font-size: 0.92rem;
        line-height: 1.55;
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


# Load project statistics
kpis = load_dashboard_kpis()

stable_counters = get_kpi(
    kpis,
    "cycling_stable_panel_counters",
)

cycling_change = get_kpi(
    kpis,
    "cycling_change_pct",
)

stop_areas = get_kpi(
    kpis,
    "public_transport_stop_areas",
)

transport_routes = get_kpi(
    kpis,
    "public_transport_routes",
)


# Header
st.title("Methodology")

st.markdown(
    "**How the cycling, road disruption and public transport data "
    "were prepared for the dashboard.**"
)

st.caption(
    "The raw datasets are processed and checked before they are "
    "loaded into Streamlit."
)


# Project scope
st.subheader("Project scope")

overview_1, overview_2, overview_3, overview_4 = st.columns(4)

with overview_1:
    st.metric(
        "Cycling data",
        "2012–2025",
    )

with overview_2:
    st.metric(
        "Stable cycling panel",
        (
            f"{int(stable_counters)} counters"
            if stable_counters is not None
            else "—"
        ),
    )

with overview_3:
    st.metric(
        "Public transport stop areas",
        (
            f"{int(stop_areas):,}"
            if stop_areas is not None
            else "—"
        ),
    )

with overview_4:
    st.metric(
        "Public transport routes",
        (
            f"{int(transport_routes):,}"
            if transport_routes is not None
            else "—"
        ),
    )


st.divider()


# Data pipeline
st.subheader("Data pipeline")

st.markdown(
    """
    Raw files and dashboard-ready data are kept separate.
    The larger Excel and GTFS files are cleaned and aggregated before
    Streamlit starts, so the application only needs to load the processed
    tables used by the charts.
    """
)

p1, p2, p3, p4, p5 = st.columns(5)


with p1:
    st.markdown(
        """
        <div class="pipeline-step">
            <div class="pipeline-number">01–02</div>
            <div class="pipeline-title">Inspect</div>
            <div class="pipeline-text">
                Check fields, timestamps,
                geometry and GTFS tables.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with p2:
    st.markdown(
        """
        <div class="pipeline-step">
            <div class="pipeline-number">03–06</div>
            <div class="pipeline-title">Prepare</div>
            <div class="pipeline-text">
                Clean the sources, standardise fields
                and assign locations to districts.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with p3:
    st.markdown(
        """
        <div class="pipeline-step">
            <div class="pipeline-number">07</div>
            <div class="pipeline-title">Analyse</div>
            <div class="pipeline-text">
                Calculate trends, hourly profiles,
                district summaries and KPIs.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with p4:
    st.markdown(
        """
        <div class="pipeline-step">
            <div class="pipeline-number">Processed data</div>
            <div class="pipeline-title">Save</div>
            <div class="pipeline-text">
                Store the results as lightweight
                Parquet and GeoJSON files.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with p5:
    st.markdown(
        """
        <div class="pipeline-step">
            <div class="pipeline-number">Streamlit</div>
            <div class="pipeline-title">Display</div>
            <div class="pipeline-text">
                Load the processed tables
                into the dashboard pages.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.code(
    """
data/raw
   ↓
scripts/01–02   Inspect
   ↓
scripts/03–06   Clean, transform and process spatial data
   ↓
data/processed
   ↓
scripts/07      Build analytical summaries
   ↓
data/processed/analytics
   ↓
src/load_data.py
   ↓
Streamlit dashboard
""".strip(),
    language="text",
)


st.divider()


# Data sources
st.subheader("Data sources")

source_1, source_2 = st.columns(2)
source_3, source_4 = st.columns(2)


with source_1:
    st.markdown(
        """
        <div class="source-card">
            <div class="source-title">🚲 Berlin cycling counters</div>
            <div class="source-text">
                Hourly cycling counts from 2012 to 2025, together with
                counter coordinates and installation dates. These data are
                used for the long-term index, hourly profiles and monitored
                district comparisons.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with source_2:
    st.markdown(
        """
        <div class="source-card">
            <div class="source-title">🚧 Berlin road disruptions</div>
            <div class="source-text">
                Roadworks and closure records with start and end times,
                street information, closure type and geometry. These records
                are used on the Current Conditions page.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with source_3:
    st.markdown(
        """
        <div class="source-card">
            <div class="source-title">🗺️ Berlin district boundaries</div>
            <div class="source-text">
                Official Bezirk polygons used to assign cycling counters,
                road disruption events and public transport locations
                to Berlin's twelve districts.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with source_4:
    st.markdown(
        """
        <div class="source-card">
            <div class="source-title">🚇 VBB Static GTFS</div>
            <div class="source-text">
                Stops, routes, trips, stop times and service calendars for
                the wider VBB network. The regional feed is filtered to
                Berlin before the public transport summaries are calculated.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.divider()


# Data-quality decisions
st.subheader("Data-quality decisions")

st.markdown(
    """
    Inspection of the raw files revealed several issues that needed to be
    resolved before the data could be compared or mapped.
    """
)


with st.expander(
    "1. Cycling worksheet year validation",
    expanded=True,
):
    st.markdown(
        """
        The worksheet named **Jahresdatei 2012** contains timestamps from
        both **2012 and 2013**.

        Because a separate 2013 worksheet also exists, reading the sheets
        without checking the dates would count the 2013 records twice.

        During preparation, each annual worksheet is therefore restricted
        to the calendar year stated in its name.
        """
    )


with st.expander("2. Historical cycling station IDs"):
    st.markdown(
        """
        Some older worksheets use station IDs that no longer match the
        current station metadata.

        These historical IDs are mapped to the current station IDs.
        The original ID is also kept in `raw_station_id`, so the mapping
        can still be traced back to the source data.
        """
    )


with st.expander("3. Missing cycling data is not zero"):
    st.markdown(
        """
        A missing hourly value does not mean that no cyclists passed
        the counter.

        Missing observations are kept as missing rather than replaced
        with zero. The preparation step also distinguishes between periods
        before a counter was installed and missing observations while it
        was active.

        A counter-day is used in the analysis only when at least
        **90% of its expected hourly observations** are available.
        """
    )


with st.expander("4. Stable cycling counter panel"):
    if cycling_change is not None:
        st.markdown(
            f"""
            Berlin added cycling counters over time. Comparing totals from all
            available counters would therefore mix changes in cycling activity
            with changes in the number of counters.

            The long-term index uses the same
            **{int(stable_counters) if stable_counters is not None else 24} counters**
            from **2017 to 2025**.

            For this group of counters, average daily cycling activity in 2025
            was approximately **{cycling_change:+.1f}%** higher than in 2017.
            """
        )
    else:
        st.markdown(
            """
            The long-term cycling index uses the same set of counters
            throughout 2017 to 2025.
            """
        )


with st.expander("5. GTFS transport mode classification"):
    st.markdown(
        """
        VBB uses extended GTFS route-type codes.

        These codes are grouped into six modes used in the dashboard:

        - Bus
        - Tram
        - U-Bahn
        - S-Bahn
        - Regional Rail
        - Ferry

        Without this mapping, many VBB routes would not be classified
        correctly using the standard GTFS categories alone.
        """
    )


with st.expander("6. GTFS platform records and stop areas"):
    if stop_areas is not None:
        st.markdown(
            f"""
            Rows in `stops.txt` can represent platforms, boarding positions
            or larger station areas. Counting every row as a separate stop
            would therefore overstate the number of physical locations.

            The preparation step uses `parent_station` where possible and
            derives a common VBB stop-area ID for related platform records.

            After this step, the Berlin dataset contains
            **{int(stop_areas):,} stop areas**.
            """
        )
    else:
        st.markdown(
            """
            Platform-level GTFS records are combined into common
            stop areas before they are counted.
            """
        )


with st.expander(
    "7. GTFS service calendars and after-midnight times"
):
    st.markdown(
        """
        GTFS service dates come from both `calendar.txt` and
        `calendar_dates.txt`. Both are used so that regular schedules
        and date-specific exceptions are included.

        GTFS times can also extend beyond 24:00. For example,
        `25:30:00` represents 01:30 on the following clock day.

        These times are shifted to the correct hour and weekday before
        the hourly service profiles are calculated.
        """
    )


with st.expander(
    "8. Road disruption status and spatial scope"
):
    st.markdown(
        """
        Road disruption status is calculated from the published start
        and end times and assigned as **Active**, **Future** or **Expired**.

        Representative points are created for the map while the original
        source geometries are kept in the processed data.

        Two source events fall outside Berlin's official district polygons.
        They are excluded from Berlin-level KPIs and district comparisons.
        """
    )


st.divider()


# Metric definitions
st.subheader("Metric definitions")

metric_table = pd.DataFrame(
    [
        {
            "Metric": "Cycling index",
            "Definition": (
                "Average daily cycling activity per counter "
                "for the stable 2017–2025 panel."
            ),
            "Interpretation": (
                "2017 = 100. A value above 100 means activity "
                "was higher than the 2017 level."
            ),
        },
        {
            "Metric": "Cycling peak hour",
            "Definition": (
                "Hour with the highest average cycling count "
                "per monitored counter."
            ),
            "Interpretation": (
                "Describes when activity is highest at the monitored counters."
            ),
        },
        {
            "Metric": "Active road disruption",
            "Definition": (
                "Road event whose validity period includes "
                "the snapshot time."
            ),
            "Interpretation": (
                "Counts recorded disruption events, not congestion or delay."
            ),
        },
        {
            "Metric": "Public transport stop area",
            "Definition": (
                "A stop or station area created by combining related "
                "GTFS platform and parent-station records."
            ),
            "Interpretation": (
                "Used instead of counting every GTFS platform record "
                "as a separate location."
            ),
        },
        {
            "Metric": "Public transport service intensity",
            "Definition": (
                "Average scheduled stop departures for the selected "
                "hour, day, mode or district."
            ),
            "Interpretation": (
                "Describes scheduled service, not passenger numbers "
                "or unique vehicles."
            ),
        },
        {
            "Metric": "Weekend / weekday ratio",
            "Definition": (
                "Typical weekend service intensity divided by "
                "typical weekday service intensity."
            ),
            "Interpretation": (
                "For example, 80% means weekend scheduled service "
                "is 80% of the weekday level."
            ),
        },
    ]
)

st.dataframe(
    metric_table,
    hide_index=True,
    width="stretch",
    row_height=72,
    column_config={
        "Metric": st.column_config.TextColumn(
            "Metric",
            width="medium",
        ),
        "Definition": st.column_config.TextColumn(
            "Definition",
            width="large",
        ),
        "Interpretation": st.column_config.TextColumn(
            "Interpretation",
            width="large",
        ),
    },
)


st.divider()


# Limitations
st.subheader("Limitations")

st.markdown(
    """
    **Cycling counters are not evenly distributed across Berlin.**  
    Some districts have more monitored locations than others. District
    averages therefore describe the counters in the data, not total cycling
    activity across the district.

    **Counters only measure activity at fixed locations.**  
    Trips that do not pass a monitored counter are not included.

    **Road disruption records do not measure congestion.**  
    The number of recorded events does not tell us how much delay they cause.

    **Road disruption data is a snapshot.**  
    Active and future event counts will change when the source data is updated.

    **GTFS describes the published timetable.**  
    It does not contain passenger numbers, occupancy, delays, cancellations
    or actual vehicle positions.

    **District counts depend partly on geography.**  
    District size, network density and the amount of transport infrastructure
    all affect absolute counts.
    """
)


st.divider()


# Reproducing the analysis
st.subheader("Reproducing the analysis")

st.markdown(
    """
    The processed datasets can be rebuilt by running the scripts
    in order from the project root.
    """
)

st.code(
    """
python scripts/01_inspect_data.py
python scripts/02_inspect_details.py
python scripts/03_prepare_boundaries.py
python scripts/04_prepare_cycling.py
python scripts/05_prepare_roadworks.py
python scripts/06_prepare_gtfs.py
python scripts/07_exploratory_analysis.py
""".strip(),
    language="bash",
)

st.markdown(
    """
    Start the dashboard locally with:
    """
)

st.code(
    "streamlit run app.py",
    language="bash",
)


# Technical stack
st.subheader("Technical stack")

(
    processing_col,
    spatial_col,
    dashboard_col,
    formats_col,
    transport_col,
    deployment_col,
) = st.columns([1.3, 1, 1, 1, 1, 0.8])

with processing_col:
    st.markdown("**Data processing**")
    st.markdown("Python  \nPandas  \nNumPy  \nOpenPyXL  \nPyArrow")

with spatial_col:
    st.markdown("**Spatial processing**")
    st.markdown("GeoPandas")

with dashboard_col:
    st.markdown("**Dashboard**")
    st.markdown("Streamlit  \nPlotly  \nPyDeck")

with formats_col:
    st.markdown("**Data formats**")
    st.markdown("Excel  \nParquet  \nGeoJSON")

with transport_col:
    st.markdown("**Transport data**")
    st.markdown("GTFS Static")

with deployment_col:
    st.markdown("**Deployment**")
    st.markdown("Docker")

# Final note
st.divider()

st.markdown(
    """
    ### Before a metric reaches the dashboard

    Each metric is checked against the structure and limitations of its
    source data first. The inspection, cleaning and analysis steps are kept
    separate from the Streamlit pages so that the calculations can be checked
    independently of the visualisation.
    """
)

st.caption(
    "Berlin Mobility Dashboard · Data analysis, spatial processing "
    "and interactive visualisation · Jing XU "
)