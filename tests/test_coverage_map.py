"""Verify map geometry does not change or expand reviewed coverage evidence."""

import json
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from src.coverage_map import coverage_map_features

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def coverage():
    snapshot = json.loads((ROOT / "data/processed/dashboard_snapshot.json").read_text())
    return pd.DataFrame.from_records(snapshot["queries"]["coverage"]["rows"])


@pytest.fixture
def geometry():
    return json.loads((ROOT / "data/raw/world_boundaries.geojson").read_text())


def test_map_keeps_exact_reviewed_coverage_and_source_capabilities(coverage, geometry):
    expected = coverage.set_index("country_iso3").to_dict(orient="index")
    mapped = coverage_map_features(coverage, geometry)
    assert mapped["type"] == "FeatureCollection"
    assert len(mapped["features"]) == 174
    codes = [feature["properties"]["country_iso3"] for feature in mapped["features"]]
    assert len(codes) == len(set(codes))
    for feature in mapped["features"]:
        properties = feature["properties"]
        assert properties == {"country_iso3": properties["country_iso3"], **expected[properties["country_iso3"]]}
        assert "POP_EST" not in properties
        assert "GDP_MD" not in properties
    assert set(codes).issubset(expected)


def test_france_and_norway_keep_their_reviewed_rows_with_natural_earth_fallback(coverage, geometry):
    mapped = coverage_map_features(coverage, geometry)
    properties = {feature["properties"]["country_iso3"]: feature["properties"] for feature in mapped["features"]}
    for code in ("FRA", "NOR"):
        original = next(feature for feature in geometry["features"] if feature["properties"]["ADM0_A3"] == code)
        assert original["properties"]["ISO_A3"] == "-99"
        assert properties[code] == coverage.loc[coverage["country_iso3"].eq(code)].iloc[0].to_dict()
    admin_fallback = deepcopy(geometry)
    for feature in admin_fallback["features"]:
        if feature["properties"]["ADM0_A3"] in {"FRA", "NOR"}:
            feature["properties"]["ISO_A3_EH"] = "-99"
    fallback_codes = {feature["properties"]["country_iso3"] for feature in coverage_map_features(coverage, admin_fallback)["features"]}
    assert {"FRA", "NOR"}.issubset(fallback_codes)


def test_unresolved_boundaries_are_not_given_an_invented_status(coverage, geometry):
    unresolved = [
        feature for feature in geometry["features"]
        if feature["properties"]["ADM0_A3"] in {"CYN", "SOL", "KOS"}
    ]
    assert len(unresolved) == 3
    unresolved[0]["properties"]["SOV_A3"] = "CYP"
    result = coverage_map_features(coverage, {"type": "FeatureCollection", "features": unresolved})
    assert result["features"] == []
    assert len(geometry["features"]) == 177


def test_small_territories_remain_in_full_249_row_roster(coverage, geometry):
    before = coverage.copy(deep=True)
    mapped = coverage_map_features(coverage, geometry)
    mapped_codes = {feature["properties"]["country_iso3"] for feature in mapped["features"]}
    assert len(coverage) == 249
    assert "SGP" in set(coverage["country_iso3"])
    assert "SGP" not in mapped_codes
    assert len(set(coverage["country_iso3"]) - mapped_codes) == 75
    pd.testing.assert_frame_equal(coverage, before)


def test_filtered_map_retains_exact_status_and_does_not_relabel_other_countries(coverage, geometry):
    selected = coverage.loc[coverage["audit_status"].eq("Data extracted")].copy()
    mapped = coverage_map_features(selected, geometry)
    assert mapped["features"]
    assert {feature["properties"]["audit_status"] for feature in mapped["features"]} == {"Data extracted"}
    assert {feature["properties"]["country_iso3"] for feature in mapped["features"]}.issubset(set(selected["country_iso3"]))
    empty = coverage_map_features(coverage.iloc[:0], geometry)
    assert empty == {"type": "FeatureCollection", "features": []}


def test_output_geometry_and_evidence_are_independent_copies(coverage, geometry):
    before_coverage = coverage.copy(deep=True)
    before_geometry = deepcopy(geometry)
    result = coverage_map_features(coverage, geometry)
    result["features"][0]["properties"]["audit_status"] = "changed locally"
    result["features"][0]["geometry"]["coordinates"] = []
    pd.testing.assert_frame_equal(coverage, before_coverage)
    assert geometry == before_geometry


def test_duplicate_country_rows_fail_instead_of_selecting_an_arbitrary_status(coverage, geometry):
    duplicate = pd.concat([coverage, coverage.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="one row"):
        coverage_map_features(duplicate, geometry)
