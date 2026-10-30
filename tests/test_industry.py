"""Reject incompatible public-data definitions before comparing them."""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.updates import ssb_format_rows
from src.validation import validate_industry_metrics

ROOT = Path(__file__).resolve().parents[1]


def test_industry_series_cannot_mix_currencies():
    frame = pd.read_csv(ROOT / "data/curated/industry_metrics.csv")
    frame.loc[frame.index[0], "unit"] = "GBP million"
    with pytest.raises(ValueError, match="Incompatible industry definitions"):
        validate_industry_metrics(frame, set(frame.source_id))


@pytest.mark.parametrize("alteration", ["broader_audio", "extra_population", "future_wave"])
def test_ssb_unreviewed_definition_is_rejected(tmp_path, alteration):
    payload = json.loads((ROOT / "data/raw/ssb_formats_since2022.json").read_text())
    if alteration == "broader_audio":
        payload["dimension"]["Media"]["category"]["label"]["01"] = "Audio media"
    elif alteration == "extra_population":
        payload["id"].append("Sex")
        payload["size"].append(1)
        payload["dimension"]["Sex"] = {"category": {"index": {"F": 0}, "label": {"F": "Women"}}}
    else:
        years = payload["dimension"]["Tid"]["category"]["index"]
        years["2099"] = years.pop("2025")
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        ssb_format_rows(path)


@pytest.mark.parametrize("changed_definition", ["denominator", "population", "period"])
def test_equal_percentage_cannot_hide_a_changed_survey_definition(changed_definition):
    from src.validation import reject_conflicting_definitions

    row = pd.read_csv(ROOT / "data/curated/format_history_extra.csv").iloc[:1]
    copy = row.copy()
    copy[changed_definition] = "A different eligible population or recall period"
    combined = pd.concat([row, copy], ignore_index=True)
    with pytest.raises(ValueError, match="Conflicting observation values or definitions"):
        reject_conflicting_definitions(combined, ["country_iso3", "year", "format_label"])


def test_later_wave_keeps_earlier_sample_and_unreported_genres():
    history = pd.read_csv(ROOT / "data/processed/format_history.csv")
    baseline = pd.read_csv(ROOT / "data/curated/format_profiles.csv")
    old = baseline[baseline.country_iso3.eq("CAN")].sort_values("format_label")
    retained = history[history.country_iso3.eq("CAN") & history.year.eq(2024)].sort_values("format_label")
    pd.testing.assert_frame_equal(
        old.reset_index(drop=True), retained[old.columns].reset_index(drop=True), check_dtype=False
    )
    genres = pd.read_csv(ROOT / "data/processed/genre_history.csv")
    missing = genres[
        genres.country_iso3.eq("CAN")
        & genres.year.eq(2025)
        & genres.format_label.eq("Audiobook")
        & genres.genre.eq("Comics or Graphic Novels")
    ]
    assert len(missing) == 2 and missing.participation.isna().all()


def test_expanded_industry_rows_match_reviewed_extraction_receipts():
    frame = pd.read_csv(ROOT / "data/curated/industry_metrics.csv")
    review = json.loads((ROOT / "data/curated/industry_review_20261025.json").read_text())
    assert len(frame) == 98
    assert frame.country_iso3.nunique() == 29
    assert frame.series_id.nunique() == 42
    indexed = frame.set_index(["series_id", "year"])
    for expected in review["added_observations"]:
        actual = indexed.loc[(expected["series_id"], expected["year"])]
        assert actual.value == pytest.approx(expected["value"])
        for field in ["unit", "country_iso3", "scope", "source_id", "source_url", "evidence_locator", "publication_date"]:
            assert str(actual[field]) == str(expected[field])
    registry = {source["source_id"]: source for source in json.loads((ROOT / "data/source_register.json").read_text())}
    for row in frame.itertuples():
        assert row.country_iso3 in registry[row.source_id]["country_iso3"].split(";")


def test_original_currency_units_and_nominal_components_reconcile():
    frame = pd.read_csv(ROOT / "data/curated/industry_metrics.csv")
    review = json.loads((ROOT / "data/curated/industry_review_20261025.json").read_text())
    japan = review["root_reviews"]["japan"]
    for kind, originals in japan["original_values"].items():
        rows = frame.loc[frame.series_id.eq(f"jp_ajpea_{kind}_sales_2026_vintage")].sort_values("year")
        assert rows.unit.eq("JPY million").all()
        assert rows.value.tolist() == [value * 100 for value in originals]
    brazil = frame.loc[frame.country_iso3.eq("BRA")].pivot(index="year", columns="series_id", values="value")
    for row in brazil.itertuples():
        assert row.br_cbl_print_publisher_total_revenue == pytest.approx(
            row.br_cbl_print_publisher_market_revenue + row.br_cbl_print_publisher_government_revenue,
        )


def test_audio_and_missing_year_limits_remain_explicit():
    frame = pd.read_csv(ROOT / "data/curated/industry_metrics.csv")
    assert set(frame.loc[frame.country_iso3.eq("CAN"), "year"]) == {2022, 2024}
    assert not frame.loc[frame.country_iso3.eq("FIN"), "metric"].str.contains("audio", case=False).any()
    sweden = frame.loc[frame.series_id.eq("se_bfs_streamed_audio_retail_revenue")].sort_values("year")
    assert sweden.value.tolist() == [1163, 1274, 1366, 1418]
    assert sweden.scope.str.contains("domestic", case=False).all() or sweden.notes.str.contains("domestic", case=False).all()
    spain = frame.loc[frame.country_iso3.eq("ESP") & frame.metric.str.contains("audio", case=False)].sort_values("year")
    assert spain.value.tolist() == [3.43, 6.70, 9.98, 15.30]


def test_historical_wipo_year_precision_and_regional_scope_are_preserved():
    frame = pd.read_csv(ROOT / "data/curated/industry_metrics.csv")
    rows = frame.loc[frame.source_id.eq("wipo_publishing_2022")]
    assert len(rows) == 18
    assert rows.year.eq(2022).all()
    assert rows.publication_date.eq("2023").all()
    assert rows.unit.eq("USD million").all()
    assert rows.loc[rows.country_iso3.eq("BEL"), "scope"].str.contains("French", case=False).all()
    assert not rows.country_iso3.isin(["MEX", "KOR"]).any()
    validate_industry_metrics(frame, set(frame.source_id))


@pytest.mark.parametrize("value", ["unknown", "2023-13-01", "2023-02-30"])
def test_invalid_industry_publication_date_is_rejected(value):
    frame = pd.read_csv(ROOT / "data/curated/industry_metrics.csv")
    frame.loc[frame.index[0], "publication_date"] = value
    with pytest.raises(ValueError, match="publication date"):
        validate_industry_metrics(frame, set(frame.source_id))
