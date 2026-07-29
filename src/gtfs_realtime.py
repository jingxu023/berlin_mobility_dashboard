"""Utilities for fetching and parsing the VBB GTFS-Realtime feed.

The live feed can have incomplete coverage, so the dashboard should show
freshness and data-health information instead of treating missing data as
normal service.
"""
from datetime import datetime, timezone
import requests

VBB_GTFS_RT_URL = "https://production.gtfsrt.vbb.de/data"

def fetch_gtfs_rt(timeout: int = 15) -> bytes:
    """Download the raw GTFS-Realtime Protocol Buffer payload."""
    response = requests.get(VBB_GTFS_RT_URL, timeout=timeout)
    response.raise_for_status()
    return response.content

def utc_now_iso() -> str:
    """Return the current UTC timestamp for data-health logging."""
    return datetime.now(timezone.utc).isoformat()
