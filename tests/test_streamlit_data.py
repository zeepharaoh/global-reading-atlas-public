"""Check the companion preserves the reviewed evidence and its decision limits."""

import json
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from src.streamlit_data import (
    QUERY_IDS,
    decision_screen,
    load_snapshot,
    query_frame,
    select_rows,
    source_detail,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def snapshot():
    return load_snapshot(ROOT / "data/processed/dashboard_snapshot.json")


def test_all_reviewed_rows_are_preserved(snapshot):
    assert set(QUERY_IDS).issubset(snapshot["queries"])
    for query_id in QUERY_IDS:
        expected = pd.DataFrame.from_records(snapshot["queries"][query_id]["rows"])
        pd.testing.assert_frame_equal(query_frame(snapshot, query_id), expected)


def test_germany_missing_result_is_not_zero(snapshot):
    germany = select_rows(query_frame(snapshot, "europe"), {"country_iso3": "DEU"})
    assert len(germany) == 1
    assert germany["participation"].isna().all()
    assert germany.iloc[0]["status_flag"] == "u"


def test_canadian_missing_genre_survives_exact_filters(snapshot):
    rows = select_rows(query_frame(snapshot, "genre_history"), {
        "country_iso3": "CAN", "year": 2024, "format_label": "Audiobook",
        "genre_scope": "Book fiction genres", "genre": "Comics or Graphic Novels",
    })
    assert len(rows) == 1
    assert rows["participation"].isna().all()
    assert "subgroup" in rows.iloc[0]["notes"]


def test_history_scope_keeps_only_observed_years(snapshot):
    frame = query_frame(snapshot, "audiobook_history")
    assert frame["year"].ge(2022).all()
    sweden = select_rows(frame, {"country_iso3": "SWE", "comparison_group": "Daily population reach"})
    assert sweden["year"].tolist() == [2022, 2023, 2024, 2025]
    assert sweden["participation"].tolist() == [14.0, 15.0, 15.0, 15.0]
    assert 2026 not in sweden["year"].tolist()


def test_lists_are_exact_filters_without_pooling(snapshot):
    frame = query_frame(snapshot, "format_history")
    selected = select_rows(frame, {"country_iso3": "CAN", "year": 2025, "format_label": ["Print", "Audiobook"]})
    assert len(selected) == 2
    assert set(selected["format_label"]) == {"Print", "Audiobook"}
    assert set(selected["country_iso3"]) == {"CAN"}
    assert select_rows(frame, {"format_label": []}).empty
    assert select_rows(frame, {"year": "2025"}).empty


def test_snapshot_and_frames_are_not_mutated(snapshot):
    before = deepcopy(snapshot)
    frame = query_frame(snapshot, "audiobook_history")
    selected = select_rows(frame, {"country_iso3": "CAN"})
    selected.loc[:, "participation"] = 0.0
    frame.loc[:, "notes"] = "modified locally"
    source = source_detail(snapshot, "audiobook_history")
    source["links"][0]["label"] = "changed locally"
    assert snapshot == before


def test_entry_excludes_existing_group_and_keeps_canada_unverified(snapshot):
    screen = decision_screen(query_frame(snapshot, "audio_market_evidence"), "new_entry")
    assert len(screen) == 8
    known = screen[screen["country_iso3"] != "CAN"]
    assert known["group_classification"].eq("existing_group").all()
    assert known["decision_status"].eq("Excluded: existing Group market").all()
    canada = screen[screen["country_iso3"] == "CAN"].iloc[0]
    assert canada["group_classification"] == "unverified"
    assert "unverified" in canada["decision_status"]
    assert not screen["group_classification"].eq("candidate").any()


def test_growth_is_separate_and_routes_are_exact(snapshot):
    frame = query_frame(snapshot, "audio_market_evidence")
    before = frame.copy(deep=True)
    screen = decision_screen(frame, "existing_growth")
    assert screen["decision_route"].eq("existing_growth").all()
    assert screen["decision_status"].str.contains("assess growth").sum() == 7
    pd.testing.assert_frame_equal(frame, before)
    with pytest.raises(ValueError, match="Decision route"):
        decision_screen(frame, "all")


def test_only_explicit_absence_can_enter_candidate_screen():
    frame = pd.DataFrame([
        {"decision_route": "new_entry", "group_presence": "Confirmed no existing Group market"},
        {"decision_route": "new_entry", "group_presence": "Available internationally"},
        {"decision_route": "new_entry", "group_presence": None},
    ])
    screen = decision_screen(frame, "new_entry")
    assert screen["group_classification"].tolist() == ["candidate", "unverified", "unverified"]
    assert "further evidence required" in screen.iloc[0]["decision_status"]


def test_unknown_query_and_columns_fail_explicitly(snapshot):
    with pytest.raises(KeyError):
        query_frame(snapshot, "not_registered")
    with pytest.raises(KeyError):
        source_detail(snapshot, "not_registered")
    with pytest.raises(KeyError, match="Unknown filter columns"):
        select_rows(query_frame(snapshot, "europe"), {"not_a_column": "CAN"})


@pytest.mark.parametrize("mutation,match", [
    (lambda value: value.pop("queries"), "queries object"),
    (lambda value: value["queries"].pop("europe"), "missing queries"),
    (lambda value: value["queries"]["europe"].update(rows={}), "scalar row"),
    (lambda value: value["queries"]["europe"].update(rows=[{"invalid": []}]), "scalar row"),
    (lambda value: value["queries"]["europe"].update(source=[]), "source metadata"),
    (lambda value: value["queries"]["europe"].update(methods={}), "methods list"),
])
def test_malformed_envelopes_are_rejected(snapshot, tmp_path, mutation, match):
    mutation(snapshot)
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        load_snapshot(path)


@pytest.mark.parametrize("number", ["NaN", "Infinity", "1e309"])
def test_nonfinite_json_is_rejected(tmp_path, number):
    path = tmp_path / "snapshot.json"
    path.write_text('{"queries":{}, "value":' + number + '}', encoding="utf-8")
    with pytest.raises(ValueError, match="nonfinite"):
        load_snapshot(path)
