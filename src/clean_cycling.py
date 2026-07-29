"""Cleaning pipeline for Berlin hourly cycling counter data.

Typical tasks:
- standardize column names
- parse timestamps
- reshape wide data if needed
- handle missing values
- derive hour, weekday/weekend, month, and year
- export clean hourly and daily Parquet files
"""

def clean_cycling_data(df):
    """Return a cleaned cycling DataFrame.

    Replace this starter function after inspecting the actual Excel columns.
    """
    return df.copy()
