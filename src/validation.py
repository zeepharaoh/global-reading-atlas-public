"""Fail early when evidence loses its meaning, provenance, or unique grain."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def validate_observations(frame: pd.DataFrame, source_ids: set[str], *, genres: bool = False) -> None:
    required = [
        "country_iso3",
        "year",
        "format_label",
        "participation",
        "denominator",
        "population",
        "period",
        "source_id",
        "source_url",
        "evidence_locator",
    ]
    keys = ["country_iso3", "year", "format_label"]
    if genres:
        required += ["genre", "genre_scope"]
        keys += ["genre_scope", "genre"]
    missing = set(required) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    if frame.duplicated(keys).any():
        raise ValueError("Duplicate observation grain")
    if frame[[col for col in required if col != "participation"]].isna().any().any():
        raise ValueError("Missing provenance or denominator")
    if not frame.participation.dropna().between(0, 100).all():
        raise ValueError("Participation must be a percentage in [0, 100]")
    if not set(frame.source_id).issubset(source_ids):
        raise ValueError("Unknown source ID")
    if not frame.source_url.str.startswith("https://").all():
        raise ValueError("Missing HTTPS evidence link")


def reject_conflicting_definitions(frame: pd.DataFrame, keys: list[str]) -> None:
    """Equal percentages do not make different populations the same observation."""
    definitions = [
        column
        for column in [
            "participation",
            "denominator",
            "population",
            "period",
            "comparison_group",
            "source_id",
        ]
        if column in frame.columns and column not in keys
    ]
    if frame.groupby(keys, dropna=False)[definitions].nunique(dropna=False).gt(1).any().any():
        raise ValueError("Conflicting observation values or definitions")


def validate_industry_metrics(frame: pd.DataFrame, source_ids: set[str]) -> None:
    """Do not put currencies, populations or different measures into one series."""
    required = [
        "series_id",
        "country_iso3",
        "country",
        "year",
        "metric",
        "value",
        "unit",
        "scope",
        "source_id",
        "source_url",
        "evidence_locator",
        "publication_date",
        "notes",
    ]
    if not set(required).issubset(frame.columns) or frame[required].isna().any().any():
        raise ValueError("Industry metric lost its scope or evidence")
    if frame.duplicated(["series_id", "year"]).any():
        raise ValueError("Duplicate industry series observation")
    if not frame.value.ge(0).all() or not np.isfinite(frame.value).all():
        raise ValueError("Industry metric must be a finite nonnegative observation")
    if not frame.year.between(2022, datetime.now(timezone.utc).year).all():
        raise ValueError("Industry observation outside the requested period")
    if not set(frame.source_id).issubset(source_ids) or not frame.source_url.str.startswith("https://").all():
        raise ValueError("Industry metric needs a registered HTTPS source")
    dates = pd.to_datetime(frame.publication_date, errors="coerce", utc=True)
    if dates.isna().any() or dates.gt(pd.Timestamp.now(tz="UTC")).any():
        raise ValueError("Industry publication date missing or in the future")
    definitions = ["country_iso3", "country", "metric", "unit", "scope", "source_id"]
    if frame.groupby("series_id")[definitions].nunique().gt(1).any().any():
        raise ValueError("Incompatible industry definitions within one series")


def validate_companies(frame: pd.DataFrame) -> None:
    required = [
        "company_id",
        "company",
        "formats",
        "business_model",
        "geographic_scope",
        "public_data_status",
        "source_url",
        "reviewed_on",
        "notes",
    ]
    if not set(required).issubset(frame.columns) or frame[required].isna().any().any():
        raise ValueError("Company record lost its business scope or source")
    if not frame.company_id.is_unique or not frame.source_url.str.startswith("https://").all():
        raise ValueError("Company records need unique IDs and HTTPS sources")
    dates = pd.to_datetime(frame.reviewed_on, errors="coerce", utc=True)
    if dates.isna().any() or dates.gt(pd.Timestamp.now(tz="UTC")).any():
        raise ValueError("Company review date missing or in the future")


def validate_cached_evidence(root: Path = ROOT) -> dict:
    """Independent reconciliation of cached inputs and derived analysis."""
    from .audit import eurostat_frame

    raw = root / "data/raw"
    data = root / "data/processed"
    receipts = json.loads((raw / "download_receipt.json").read_text())
    for receipt in receipts:
        actual = hashlib.sha256((root / receipt["file"]).read_bytes()).hexdigest()
        if actual != receipt["sha256"]:
            raise ValueError(f"Cached input changed: {receipt['file']}")
    checked_apis = 0
    state_path = raw / "source_check_state.json"
    if state_path.exists():
        state = {row["source_id"]: row for row in json.loads(state_path.read_text())}
        for source_id, filename, hash_field in [
            ("eurostat", "eurostat_ilc_scp27_since2022.json", "sha256"),
            ("ssb_no", "ssb_formats_since2022.json", "api_sha256"),
        ]:
            path = raw / filename
            expected = state.get(source_id, {}).get(hash_field)
            if path.exists() and expected:
                if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise ValueError(f"API cache disagrees with its retrieval receipt: {filename}")
                checked_apis += 1
    eu, _ = eurostat_frame(raw / "eurostat_ilc_scp27_2022.json")
    baseline = eu[(eu.sex == "T") & (eu.age == "Y_GE16") & (eu.isced11 == "TOTAL")]
    groups = baseline.pivot(index="geo", columns="n_book", values="value")
    complete = groups.dropna()
    if not np.allclose(complete.sum(axis=1), 100, atol=0.21, rtol=0):
        raise ValueError("Book-count categories do not reconcile to 100% within rounding")
    rates = pd.read_csv(data / "europe_participation.csv").set_index("geo")
    independent = 100 - groups["0"].reindex(rates.index)
    eligible = ~rates.status_flag.fillna("").str.contains("u")
    if not np.allclose(
        rates.loc[eligible, "participation"], independent[eligible], atol=1e-8, equal_nan=True
    ):
        raise ValueError("Derived reading rates disagree with original zero-book cells")
    if rates.loc["DE", "participation"] == 0 or pd.notna(rates.loc["DE", "participation"]):
        raise ValueError("Germany must remain missing")
    sources = set(pd.read_csv(data / "source_register.csv").source_id)
    for name, is_genre in [("format_profiles", False), ("genre_profiles", True)]:
        validate_observations(pd.read_csv(data / f"{name}.csv"), sources, genres=is_genre)
    pew = pd.read_csv(raw / "pew_formats.csv")
    if (
        not pew.loc[pew.survey_year == 2025, "method_break"].all()
        or pew.loc[pew.survey_year < 2025, "method_break"].any()
    ):
        raise ValueError("Pew survey-method break was lost")
    snapshot = json.loads((data / "dashboard_snapshot.json").read_text())
    for name in ["europe", "demographics", "format_profiles", "genre_profiles", "coverage"]:
        if not snapshot["queries"][name]["rows"]:
            raise ValueError(f"Empty dashboard query: {name}")
    for name in [
        "audiobook_evidence",
        "audiobook_history",
        "audio_market_evidence",
        "storytel_audio_2026",
        "data_freshness",
        "format_history",
        "genre_history",
        "companies",
        "industry_metrics",
    ]:
        path = data / f"{name}.csv"
        if path.exists():
            frame = pd.read_csv(path)
            rows = pd.DataFrame(snapshot["queries"][name]["rows"])

            pd.testing.assert_frame_equal(
                frame.fillna("").reset_index(drop=True),
                rows[frame.columns].fillna("").reset_index(drop=True),
                check_dtype=False,
            )
    if (data / "format_history.csv").exists():
        validate_observations(pd.read_csv(data / "format_history.csv"), sources)
    if (data / "genre_history.csv").exists():
        validate_observations(pd.read_csv(data / "genre_history.csv"), sources, genres=True)
    if (data / "industry_metrics.csv").exists():
        validate_industry_metrics(pd.read_csv(data / "industry_metrics.csv"), sources)
    if (data / "companies.csv").exists():
        validate_companies(pd.read_csv(data / "companies.csv"))
    story_path = data / "storytel_audio_2026.csv"
    if story_path.exists():
        story = pd.read_csv(story_path)
        if story.duplicated(["country_iso3", "year", "record_type", "item"]).any():
            raise ValueError("Duplicate Storytel listener observation")
        required = [
            "item",
            "record_type",
            "denominator",
            "population",
            "period",
            "source_url",
            "evidence_locator",
        ]
        if story[required].isna().any().any() or not story.participation.between(0, 100).all():
            raise ValueError("Storytel listener evidence lost its question or base")
        if not set(story.source_id).issubset(sources):
            raise ValueError("Unknown Storytel source")
        if not story.format_label.eq("Audiobook").all():
            raise ValueError("Listener questions must retain the audiobook format")
    return {
        "input_hashes_verified": len(receipts) + checked_apis,
        "category_groups_reconciled": len(complete),
        "country_rates_reconciled": int(rates.participation.notna().sum()),
        "genre_rows_validated": len(snapshot["queries"]["genre_profiles"]["rows"]),
        "genre_history_rows_validated": len(snapshot["queries"].get("genre_history", {}).get("rows", [])),
        "format_history_rows_validated": len(snapshot["queries"].get("format_history", {}).get("rows", [])),
        "company_records_validated": len(snapshot["queries"].get("companies", {}).get("rows", [])),
    }
