"""
Application entry point for the Berlin Mobility Dashboard.

Defines the global Streamlit configuration and page navigation.
"""

import streamlit as st


# Global page configuration
st.set_page_config(
    page_title="Berlin Mobility Dashboard",
    page_icon="🚇",
    layout="wide",
    initial_sidebar_state="expanded",
)



# Navigation
pages = {
    "Berlin Mobility": [
        st.Page(
            "pages/overview.py",
            title="Overview",
            icon=":material/dashboard:",
            default=True,
        ),
        st.Page(
            "pages/mobility_patterns.py",
            title="Mobility Patterns",
            icon=":material/monitoring:",
        ),
        st.Page(
            "pages/live_conditions.py",
            title="Current Conditions",
            icon=":material/traffic:",
        ),
        st.Page(
            "pages/methodology.py",
            title="Methodology",
            icon=":material/menu_book:",
        ),
    ]
}


navigation = st.navigation(
    pages
)

navigation.run()