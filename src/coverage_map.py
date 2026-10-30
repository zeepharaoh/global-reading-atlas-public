"""Join reviewed coverage rows to bundled country geometry using exact ISO codes."""

from __future__ import annotations

from copy import deepcopy

import pandas as pd

_COVERAGE_FIELDS = (
    "country_iso3", "country", "audit_status", "source_ids", "book_participation",
    "audiobook_separate", "genre_detail", "research_gap", "note",
)


def coverage_map_features(coverage: pd.DataFrame, geometry: dict) -> dict:
    """Return joined features without assigning evidence to unresolved boundaries."""
    missing = set(_COVERAGE_FIELDS) - set(coverage.columns)
    if missing:
        raise KeyError(f"Coverage map requires columns: {sorted(missing)}")
    if coverage["country_iso3"].isna().any() or not coverage["country_iso3"].is_unique:
        raise ValueError("Coverage map requires one row per nonmissing ISO country code")
    if geometry.get("type") != "FeatureCollection" or not isinstance(geometry.get("features"), list):
        raise ValueError("Coverage map geometry requires a GeoJSON FeatureCollection")

    rows = {
        row["country_iso3"]: row
        for row in coverage.loc[:, list(_COVERAGE_FIELDS)].to_dict(orient="records")
    }
    joined = []
    for feature in geometry["features"]:
        properties = feature.get("properties") or {}
        country_iso3 = next((
            properties.get(field)
            for field in ("ISO_A3", "ISO_A3_EH", "ADM0_A3")
            if properties.get(field) in rows
        ), None)
        if country_iso3 is None:
            continue
        joined.append({
            "type": "Feature",
            "geometry": deepcopy(feature["geometry"]),
            "properties": deepcopy(rows[country_iso3]),
        })
    return {"type": "FeatureCollection", "features": joined}
