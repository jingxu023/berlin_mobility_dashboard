"""Spatial-analysis helpers for joining mobility data to Berlin districts.

Examples:
- spatially join roadworks to Bezirke
- assign cycling counters to districts
- calculate district counts or rates
- prepare GeoDataFrames for choropleth maps
"""
import geopandas as gpd

def ensure_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Return a copy reprojected to EPSG:4326 for web mapping."""
    return gdf.to_crs(epsg=4326)
