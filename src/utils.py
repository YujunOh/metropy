"""Common utilities for Metropy."""
import re
import pandas as pd


def normalize_station_name(name):
    """Normalize Korean station names."""
    if pd.isna(name):
        return ""
    name = str(name)
    name = re.sub(r"\([^)]*\)", "", name)
    name = re.sub(r"\[[^\]]*\]", "", name)
    name = re.sub(r"역$", "", name)
    name = name.replace(" ", "").strip()
    return name
