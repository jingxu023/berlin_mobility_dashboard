"""Shared Plotly / PyDeck chart builders.

Centralizing chart code helps keep styling consistent across dashboard pages.
"""
import plotly.express as px

def hourly_line_chart(df, x: str, y: str, color: str | None = None):
    """Create a simple hourly mobility line chart."""
    return px.line(df, x=x, y=y, color=color)
