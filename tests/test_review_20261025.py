"""Protect the definitions in the October public source expansion."""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def rows(filename, source_id):
    frame = pd.read_csv(ROOT / "data/processed" / filename)
    return frame.loc[frame.source_id.eq(source_id)].copy()


def test_australian_population_audio_is_distinct_from_reader_subset():
    frame = rows("format_history.csv", "creative_au")
    assert frame.set_index(["year", "format_label"]).participation.to_dict() == {
        (2022, "Print"): 66, (2022, "Ebook"): 41, (2022, "Audiobook"): 34,
        (2025, "Print"): 66, (2025, "Ebook"): 36, (2025, "Audiobook"): 37,
    }
    assert frame.denominator.str.contains("General population age 15", regex=False).all()
    assert set(frame.year) == {2022, 2025}


def test_french_annual_listening_does_not_use_ever_listened_value():
    frame = rows("audiobook_history.csv", "cnl_fr")
    assert frame.participation.tolist() == [15]
    assert frame.period.tolist() == ["past_12_months"]
    assert frame.year.tolist() == [2025]


def test_audible_genres_keep_listener_base_and_exclude_combined_audio_reach():
    frame = rows("genre_history.csv", "audible_compass_2025")
    assert frame.groupby("country_iso3").size().to_dict() == {"DEU": 5, "ESP": 5, "FRA": 5, "ITA": 5}
    assert frame.format_label.eq("Audiobook").all()
    assert frame.sample_size.isna().all()
    assert frame.denominator.str.contains("listened to an audiobook", case=False).all()
    assert rows("audiobook_history.csv", "audible_compass_2025").empty


def test_mexican_book_types_preserve_reader_subset():
    frame = rows("genre_history.csv", "inegi_mx")
    assert frame.set_index("genre").participation.to_dict() == {
        "Autoayuda, superación personal o religiosos": 42.3, "Literatura": 43.1,
        "Específicos de alguna materia o profesión": 35.0, "Cultura general": 29.1,
        "Manuales, guías, recetarios o de otro tipo": 27.0,
    }
    assert frame.sample_size.isna().all()
    assert frame.format_label.eq("Paper or digital").all()
    assert not frame.format_label.eq("Audiobook").any()


def test_dutch_2026_is_observed_weekly_frequency_without_reconstructed_total():
    frame = rows("audiobook_history.csv", "kvb_nl_m75")
    assert frame.set_index("year").participation.to_dict() == {2022: 5, 2023: 6, 2024: 10, 2025: 8, 2026: 10}
    assert frame.period.eq("Weekly listening frequency").all()
    assert rows("genre_history.csv", "kvb_nl_m75").empty


def test_us_citizen_survey_is_separate_from_pew_adult_population():
    audio = rows("audiobook_history.csv", "yougov_us_2025_books")
    assert audio.participation.tolist() == [23]
    assert audio.population.str.contains("citizens", case=False).all()
    assert audio.period.str.contains("to date", case=False).all()
    genres = rows("genre_history.csv", "yougov_us_2025_books")
    assert len(genres) == 21
    assert genres.format_label.eq("All book formats").all()
    assert genres.set_index("genre").loc["Mystery and crime", "participation"] == 21
    pew = pd.read_csv(ROOT / "data/processed/us_formats.csv")
    assert pew.loc[pew.year.eq(2025) & pew.format_label.eq("Audiobook"), "participation"].tolist() == [26]


def test_unresolved_sources_have_no_accepted_observations():
    for filename in ["genre_history.csv", "audiobook_history.csv", "format_history.csv"]:
        frame = pd.read_csv(ROOT / "data/processed" / filename)
        assert not frame.source_id.isin(["uk_ofcom_2026", "new_zealand_2025", "ipl_br"]).any()
    review = json.loads((ROOT / "data/curated/review_20261025.json").read_text())
    assert review["creative_au"]["publication_date"] == "2026-06-03"
    assert review["kvb_nl_m75"]["observation_years"][-1] == 2026
