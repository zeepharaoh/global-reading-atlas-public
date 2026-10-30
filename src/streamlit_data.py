"""Read reviewed dashboard evidence without pooling populations or filling gaps."""

from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path

import pandas as pd

QUERY_IDS = (
    "europe", "demographics", "eu_benchmark", "gender_gaps", "us_formats",
    "format_profiles", "genre_profiles", "coverage", "sources",
    "audiobook_evidence", "audiobook_history", "format_history", "genre_history",
    "data_freshness", "audio_market_evidence", "storytel_audio_2026", "companies",
    "industry_metrics", "europe_history",
)


def _reject_constant(value: str) -> None:
    raise ValueError(f"Snapshot contains a nonfinite JSON value: {value}")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        _reject_constant(value)
    return number


def load_snapshot(path: str | Path) -> dict:
    """Require the reviewed query envelope and preserve every published row."""
    snapshot = json.loads(
        Path(path).read_text(encoding="utf-8"), parse_constant=_reject_constant, parse_float=_finite_float,
    )
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("queries"), dict):
        raise ValueError("Snapshot requires a queries object")
    queries = snapshot["queries"]
    missing = set(QUERY_IDS) - queries.keys()
    if missing:
        raise ValueError(f"Snapshot is missing queries: {sorted(missing)}")
    for query_id, envelope in queries.items():
        if not isinstance(query_id, str) or not isinstance(envelope, dict):
            raise ValueError("Snapshot queries require named query objects")
        rows = envelope.get("rows")
        if not isinstance(rows, list) or not all(
            isinstance(row, dict) and all(
                isinstance(key, str) and (value is None or isinstance(value, (str, int, float, bool)))
                for key, value in row.items()
            ) for row in rows
        ):
            raise ValueError(f"Query {query_id} requires a list of scalar row objects")
        if not isinstance(envelope.get("source"), dict):
            raise ValueError(f"Query {query_id} requires source metadata")
        if not isinstance(envelope.get("methods"), list):
            raise ValueError(f"Query {query_id} requires a methods list")
    return snapshot


def query_frame(snapshot: dict, query_id: str) -> pd.DataFrame:
    """Return a fresh frame; JSON null stays missing rather than becoming zero."""
    return pd.DataFrame.from_records(deepcopy(snapshot["queries"][query_id]["rows"]))


def select_rows(frame: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply exact scalar or list filters without aggregation or gap filling."""
    unknown = set(filters) - set(frame.columns)
    if unknown:
        raise KeyError(f"Unknown filter columns: {sorted(unknown)}")
    selected = pd.Series(True, index=frame.index)
    for column, value in filters.items():
        choices = value if isinstance(value, list) else [value]
        nonmissing = [item for item in choices if item is not None]
        matches = frame[column].isin(nonmissing)
        if None in choices:
            matches |= frame[column].isna()
        selected &= matches
    return frame.loc[selected].copy(deep=True)


def source_detail(snapshot: dict, query_id: str) -> dict:
    """Return independent source metadata for the displayed query."""
    return deepcopy(snapshot["queries"][query_id]["source"])


def decision_screen(frame: pd.DataFrame, route: str) -> pd.DataFrame:
    """Classify footprint evidence without presenting commercial rankings."""
    if route not in {"new_entry", "existing_growth"}:
        raise ValueError("Decision route must be new_entry or existing_growth")
    rows = select_rows(frame, {"decision_route": route})
    if "group_presence" not in rows.columns:
        raise KeyError("Unknown filter columns: ['group_presence']")
    presence = rows["group_presence"].fillna("").str.casefold().str.strip()
    existing = presence.str.contains("existing group", regex=False)
    absent = presence.isin({
        "confirmed no group presence", "confirmed no group service available",
        "confirmed no existing group market",
    })
    rows["group_classification"] = "unverified"
    rows.loc[existing, "group_classification"] = "existing_group"
    rows.loc[absent, "group_classification"] = "candidate"
    rows["decision_status"] = "Group availability remains unverified"
    if route == "new_entry":
        rows.loc[existing, "decision_status"] = "Excluded: existing Group market"
        rows.loc[absent, "decision_status"] = "Potential candidate: further evidence required"
    else:
        rows.loc[existing, "decision_status"] = "Existing Group market: assess growth separately"
        rows.loc[absent, "decision_status"] = "Outside existing Group market growth scope"
    return rows
