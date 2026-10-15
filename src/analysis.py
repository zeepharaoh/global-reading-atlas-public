"""Validated analysis tables and dashboard snapshot from cached public evidence."""

from __future__ import annotations
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / "work/matplotlib"))
from datetime import datetime, timezone
import pandas as pd
import pycountry
from .audit import eurostat_frame, country_iso3
from .validation import (
    validate_observations,
    validate_companies,
    validate_industry_metrics,
    reject_conflicting_definitions,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed"
EU_CODES = set("BE BG CZ DK DE EE IE EL ES FR HR IT CY LV LT LU HU MT NL AT PL PT RO SI SK FI SE".split())
FORMAT_LABELS = {"print": "Print", "ebook": "Ebook", "audio": "Audiobook"}


def json_rows(frame):
    return json.loads(frame.to_json(orient="records"))


def make_source(label, url, files, definition, caveats):
    return {
        "label": label,
        "provider": label,
        "links": [{"label": "Original source", "url": url}],
        "files": files,
        "classification": "public-source",
        "reviewedOn": "2026-10-08",
        "filters": caveats,
        "metricDefinitions": [{"label": "Participation (%)", "definition": definition}],
        "evidenceFlow": [
            {"title": "Source", "detail": url},
            {"title": "Population and limits", "detail": " ".join(caveats)},
        ],
    }


def build_analysis():
    DATA.mkdir(parents=True, exist_ok=True)
    eu, payload = eurostat_frame(ROOT / "data/raw/eurostat_ilc_scp27_2022.json")
    labels = {name: values["category"].get("label", {}) for name, values in payload["dimension"].items()}
    selected = eu[(eu.n_book == "0") & (eu.unit == "PC")].copy()
    selected["country_iso3"] = selected.geo.map(country_iso3)
    selected["country"] = selected.geo.map(labels["geo"])
    selected["country"] = selected.country_iso3.map(
        lambda iso: pycountry.countries.get(alpha_3=iso).name if isinstance(iso, str) else None
    ).fillna(selected.country)
    selected["participation"] = (100 - selected.value).round(1)
    selected["sex_label"] = selected.sex.map({"T": "All", "F": "Women", "M": "Men"})
    selected["age_label"] = selected.age.map(labels["age"])
    selected["education_label"] = selected.isced11.map(labels["isced11"])
    selected["scope"] = selected.geo.map(
        lambda code: "EU member" if code in EU_CODES else "Other surveyed country"
    )
    selected["year"] = 2022
    selected["source_id"] = "eurostat"
    selected["nonreader_pct"] = selected.value
    selected["reliability"] = selected.status_flag.map(
        lambda s: "Missing or unreliable" if "u" in s else "Estimated" if "e" in s else "Published"
    )
    countries = selected[selected.country_iso3.notna()].copy()

    countries.loc[countries.status_flag.str.contains("u", na=False), "participation"] = float("nan")
    base = countries[
        (countries.sex == "T") & (countries.age == "Y_GE16") & (countries.isced11 == "TOTAL")
    ].copy()
    dimensions = countries[(countries.age.isin(["Y_GE16", "Y16-29", "Y30-54", "Y55-64", "Y_GE65"]))].copy()
    cols = [
        "country_iso3",
        "country",
        "geo",
        "scope",
        "year",
        "sex",
        "sex_label",
        "age",
        "age_label",
        "isced11",
        "education_label",
        "participation",
        "nonreader_pct",
        "status_flag",
        "reliability",
        "source_id",
    ]
    base[cols].to_csv(DATA / "europe_participation.csv", index=False)
    dimensions[cols].to_csv(DATA / "europe_demographics.csv", index=False)
    benchmark = selected[
        (selected.geo == "EU27_2020")
        & (selected.sex == "T")
        & (selected.age == "Y_GE16")
        & (selected.isced11 == "TOTAL")
    ][cols].copy()
    benchmark.to_csv(DATA / "eu_benchmark.csv", index=False)
    pew = pd.read_csv(ROOT / "data/raw/pew_formats.csv")
    pew["country"] = "United States"
    pew["year"] = pew.survey_year
    pew["format_label"] = pew["format"].map(FORMAT_LABELS)
    pew["participation"] = pew.value
    pew["period"] = "Past 12 months"
    pew["population"] = "US adults age 18+"
    pew["comparison_group"] = "US annual participation"
    pew.to_csv(DATA / "us_formats.csv", index=False)
    profile_path = ROOT / "data/curated/format_profiles.csv"
    profiles = pd.read_csv(profile_path) if profile_path.exists() else pd.DataFrame()
    genre_path = ROOT / "data/curated/genre_profiles.csv"
    genres = pd.read_csv(genre_path) if genre_path.exists() else pd.DataFrame()
    source_ids = {
        source["source_id"] for source in json.loads((ROOT / "data/source_register.json").read_text())
    }
    validate_observations(profiles, source_ids)
    validate_observations(genres, source_ids, genres=True)
    if not profiles.empty:
        profiles.to_csv(DATA / "format_profiles.csv", index=False)
    if not genres.empty:
        genres.to_csv(DATA / "genre_profiles.csv", index=False)
    check_percent = [base.participation, dimensions.participation, pew.participation]
    for frame in [profiles, genres]:
        if not frame.empty:
            check_percent.append(frame.participation)
    if not all(series.dropna().between(0, 100).all() for series in check_percent):
        raise ValueError("Invalid participation percentage")
    valid = base.dropna(subset=["participation"]).sort_values("participation", ascending=False)
    women = countries[(countries.sex == "F") & (countries.age == "Y_GE16") & (countries.isced11 == "TOTAL")]
    men = countries[(countries.sex == "M") & (countries.age == "Y_GE16") & (countries.isced11 == "TOTAL")]
    gaps = women[["country_iso3", "country", "participation"]].merge(
        men[["country_iso3", "participation"]], on="country_iso3", suffixes=("_women", "_men")
    )
    gaps["gap_pp"] = (gaps.participation_women - gaps.participation_men).round(1)
    gaps.to_csv(DATA / "gender_gaps.csv", index=False)
    summary = {
        "europe_observed_countries": len(valid),
        "europe_missing_countries": base.loc[base.participation.isna(), "country"].tolist(),
        "europe_top": valid.iloc[0][["country", "participation"]].to_dict(),
        "europe_bottom": valid.iloc[-1][["country", "participation"]].to_dict(),
        "eu_benchmark": float(benchmark.participation.iloc[0]),
        "country_median": round(float(valid.participation.median()), 1),
        "women_higher_countries": int((gaps.gap_pp > 0).sum()),
        "gender_assessable_countries": int(gaps.gap_pp.notna().sum()),
        "us_2011_audio_pct": float(pew[(pew.year == 2011) & (pew["format"] == "audio")].value.iloc[0]),
        "us_2021_audio_pct": float(pew[(pew.year == 2021) & (pew["format"] == "audio")].value.iloc[0]),
        "us_2025_audio_pct": float(pew[(pew.year == 2025) & (pew["format"] == "audio")].value.iloc[0]),
    }
    (ROOT / "outputs/analysis_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    snapshot = {
        "surface": "dashboard",
        "publicViewer": True,
        "title": "Global Reading Atlas",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": "reviewed",
        "buildStatus": "updating",
        "filters": [],
        "queries": {},
    }

    def query(id, frame, source, methods):
        snapshot["queries"][id] = {"rows": json_rows(frame), "source": source, "methods": methods}

    eu_source = make_source(
        "Eurostat EU-SILC 2022",
        "https://ec.europa.eu/eurostat/databrowser/view/ilc_scp27/default/table",
        ["data/raw/eurostat_ilc_scp27_2022.json"],
        "100 minus the percentage reporting zero books in the past 12 months; all formats include audio. Age 16+, unless a displayed subgroup is selected.",
        [
            "Source includes print, ebooks and audiobooks; excludes school textbooks/work manuals.",
            "Germany is missing/unreliable; null is retained. Survey year 2022, not current reading habits.",
            "EU benchmark is an official aggregate, not the average of countries. Flags e indicate estimated values.",
            "Aggregate survey results do not provide enough design information to calculate valid confidence intervals here.",
        ],
    )
    eu_source["executedAt"] = json.loads((ROOT / "data/raw/download_receipt.json").read_text())[0][
        "retrieved_at_utc"
    ]
    eu_source["coverage"] = {"startDate": "2022-01-01", "endDate": "2022-12-31"}
    methods = [
        {
            "language": "python",
            "code": "Select n_book=0, unit=PC; participation=100-value. Baseline: sex=T, age=Y_GE16, isced11=TOTAL. Exclude geographic aggregates from country rankings. Preserve missing and u flags.",
        }
    ]
    query("europe", base[cols], eu_source, methods)
    query("demographics", dimensions[cols], eu_source, methods)
    query("eu_benchmark", benchmark, eu_source, methods)
    query(
        "gender_gaps",
        gaps,
        eu_source,
        [
            {
                "language": "python",
                "code": "Women participation minus men participation for the same country, year, age and education scope; unit percentage points.",
            }
        ],
    )
    pew_source = make_source(
        "Pew Research Center book formats",
        pew.source_url.iloc[0],
        ["data/raw/pew_formats.csv"],
        "Share of US adults reading/listening to at least part of one book in each format during the past 12 months.",
        [
            "Formats overlap; do not sum them.",
            "Phone surveys 2011–2021; web and phone in 2025. The 2025 comparison crosses a method break.",
            "Manually transcribed from the publisher Data table; no respondent microdata used.",
        ],
    )
    query(
        "us_formats",
        pew,
        pew_source,
        [
            {
                "language": "python",
                "code": "Load the publisher table extract; preserve survey years, format percentages and 2025 method_break. No interpolation.",
            }
        ],
    )
    for key, frame in [("format_profiles", profiles), ("genre_profiles", genres)]:
        if not frame.empty:
            source = {
                "label": "Validated national survey tables",
                "classification": "public-source",
                "files": [str(Path("data/curated") / (key + ".csv"))],
                "links": [
                    {"label": id, "url": group.source_url.iloc[0]} for id, group in frame.groupby("source_id")
                ],
                "filters": [
                    "Country-specific denominators and periods. Do not rank incompatible populations.",
                    "Genres are multiple response; percentages are not shares of all book consumption.",
                ],
                "metricDefinitions": [
                    {
                        "label": "Participation (%)",
                        "definition": "Published percentage in each row, using its exact reported denominator.",
                    }
                ],
                "evidenceFlow": [
                    {
                        "title": "Extraction",
                        "detail": "Manually checked original tables; every row retains source URL, evidence locator and denominator.",
                    }
                ],
            }
            query(
                key,
                frame,
                source,
                [
                    {
                        "language": "python",
                        "code": "Load curated observations without changing denominator. Retain country, format, genre, survey year and exact evidence locator.",
                    }
                ],
            )
    coverage = pd.read_csv(DATA / "coverage_matrix.csv").fillna("")
    query(
        "coverage",
        coverage,
        make_source(
            "Project public-source register",
            "https://ec.europa.eu/eurostat/databrowser/view/ilc_scp27/default/table",
            ["data/source_register.json", "data/processed/coverage_matrix.csv"],
            "Source-audit readiness for each ISO country or territory; not a reading rate.",
            [
                "249 ISO country/territory entries; initial research is not exhaustive.",
                "Not researched does not mean no public data exists.",
            ],
        ),
        [
            {
                "language": "python",
                "code": "Join reviewed source-country bindings to the ISO roster; preserve candidate, documented, extracted, missing-result and not-researched states.",
            }
        ],
    )
    query(
        "sources",
        pd.read_csv(DATA / "source_register.csv").fillna(""),
        {
            "label": "Reviewed source register",
            "files": ["data/source_register.json"],
            "filters": ["Source discovery metadata; documented does not mean data extracted."],
        },
        [],
    )
    from .updates import freshness, history

    format_history = profiles.copy()
    for filename in ["format_history_nordics.csv", "format_history_extra.csv"]:
        path = ROOT / "data/curated" / filename
        if path.exists():
            extra = pd.read_csv(path)
            validate_observations(extra, source_ids)
            format_history = pd.concat([format_history, extra], ignore_index=True)
    from .updates import ssb_format_rows

    ssb_cache = ROOT / "data/raw/ssb_formats_since2022.json"
    if ssb_cache.exists():
        format_history = pd.concat([format_history, ssb_format_rows(ssb_cache)], ignore_index=True)
    grain = ["country_iso3", "year", "format_label"]
    reject_conflicting_definitions(format_history, grain)
    format_history = format_history.drop_duplicates(grain, keep="last").sort_values(grain)
    validate_observations(format_history, source_ids)
    format_history.to_csv(DATA / "format_history.csv", index=False)
    audio_history = history(format_history)
    audio_history.to_csv(DATA / "audiobook_history.csv", index=False)
    genre_history = genres.copy()
    genre_extra = ROOT / "data/curated/genre_history_extra.csv"
    if genre_extra.exists():
        extra = pd.read_csv(genre_extra)
        validate_observations(extra, source_ids, genres=True)
        genre_history = pd.concat([genre_history, extra], ignore_index=True)
    validate_observations(genre_history, source_ids, genres=True)
    genre_history.to_csv(DATA / "genre_history.csv", index=False)
    audio = (
        audio_history.sort_values("year")
        .drop_duplicates(["country_iso3", "comparison_group"], keep="last")
        .copy()
    )
    audio["format_label"] = "Audiobook"
    audio.to_csv(DATA / "audiobook_evidence.csv", index=False)
    checked = freshness(pd.read_csv(DATA / "source_register.csv").fillna(""))
    checked.to_csv(DATA / "data_freshness.csv", index=False)
    extra_frames = [
        ("audiobook_evidence", audio),
        ("audiobook_history", audio_history),
        ("format_history", format_history),
        ("genre_history", genre_history),
        ("data_freshness", checked),
    ]
    for key in ["audio_market_evidence", "storytel_audio_2026", "companies", "industry_metrics"]:
        filename = "company_register.csv" if key == "companies" else f"{key}.csv"
        path = ROOT / "data/curated" / filename
        if path.exists():
            frame = pd.read_csv(path)
            if key == "industry_metrics":
                validate_industry_metrics(frame, source_ids)
            elif key == "companies":
                validate_companies(frame)
            frame.to_csv(DATA / f"{key}.csv", index=False)
            extra_frames.append((key, frame))
    for key, frame in extra_frames:
        query(
            key,
            frame,
            {
                "label": "Book-market evidence and source freshness",
                "classification": "public-source",
                "files": [f"data/processed/{key}.csv"],
                "links": [
                    {"label": "Original source", "url": url}
                    for url in frame.get("source_url", pd.Series(dtype=str)).drop_duplicates()
                    if url
                ],
                "filters": [
                    "Keep country, question, population and recall period together. Missing survey years stay missing.",
                    "Source check time is different from survey year. Public demand data does not establish profitable market entry.",
                ],
            },
            [
                {
                    "language": "python",
                    "code": "Read validated public observations and receipts; filter annual history to 2022 onward. Do not pool incompatible definitions or interpolate unpublished waves.",
                }
            ],
        )
    history_path = ROOT / "data/raw/eurostat_ilc_scp27_since2022.json"
    if history_path.exists():
        all_eu, _ = eurostat_frame(history_path)
        eu_history = all_eu[
            (all_eu.n_book == "0")
            & (all_eu.unit == "PC")
            & (all_eu.sex == "T")
            & (all_eu.age == "Y_GE16")
            & (all_eu.isced11 == "TOTAL")
        ].copy()
        eu_history["country_iso3"] = eu_history.geo.map(country_iso3)
        eu_history = eu_history[eu_history.country_iso3.notna()].copy()
        eu_history["country"] = eu_history.country_iso3.map(
            lambda iso: pycountry.countries.get(alpha_3=iso).name
        )
        eu_history["year"] = eu_history.time.astype(int)
        eu_history["participation"] = (100 - eu_history.value).round(1)
        eu_history.loc[eu_history.status_flag.str.contains("u", na=False), "participation"] = float("nan")
        eu_history[["country_iso3", "country", "year", "participation", "status_flag"]].to_csv(
            DATA / "europe_history.csv", index=False
        )
        query(
            "europe_history",
            eu_history[["country_iso3", "country", "year", "participation", "status_flag"]],
            eu_source,
            methods,
        )
    (DATA / "dashboard_snapshot.json").write_text(json.dumps(snapshot, indent=2, allow_nan=False) + "\n")
    dashboard_data = ROOT / "dashboard/src/data.json"
    if dashboard_data.exists():

        existing = json.loads(dashboard_data.read_text())
        for key in ["id", "artifactId", "appId", "theme"]:
            if key in existing:
                snapshot[key] = existing[key]
        dashboard_data.write_text(json.dumps(snapshot, indent=2, allow_nan=False) + "\n")
    return summary


if __name__ == "__main__":
    print(json.dumps(build_analysis(), indent=2))
