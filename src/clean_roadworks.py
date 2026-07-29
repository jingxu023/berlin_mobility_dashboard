"""Cleaning pipeline for Berlin roadworks, closures, and disruptions.

Typical tasks:
- inspect GeoJSON properties
- standardize event categories
- parse start/end dates
- remove duplicates
- validate coordinates and CRS
- export a compact processed dataset
"""

def clean_roadworks_data(gdf):
    """Return a cleaned roadworks GeoDataFrame."""
    return gdf.copy()
