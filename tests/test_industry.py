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
