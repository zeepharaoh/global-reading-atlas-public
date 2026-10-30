"""Rebuild the source audit from reviewed metadata and cached public inputs."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
import pycountry

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
PROCESSED = ROOT / "data/processed"
OUT = ROOT / "outputs"
EUROSTAT_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/ilc_scp27?lang=EN&time=2022"
)
GEOMETRY_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"
STATUS_ORDER = [
    "Not researched",
    "Reviewed, missing result",
    "Candidate only",
    "Public source documented",
    "Data extracted",
]
COLORS = dict(zip(STATUS_ORDER, ["#e5e7eb", "#bca98a", "#ebc36b", "#8cabc7", "#245b85"]))


def download(url: str, path: Path) -> dict:
    with urlopen(url, timeout=60) as response:
        content = response.read()
    path.write_bytes(content)
    return {
        "url": url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "file": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def eurostat_frame(path: Path) -> tuple[pd.DataFrame, dict]:
    payload = json.loads(path.read_text())
    ids, sizes = payload["id"], payload["size"]
    dimensions = {}
    for dim in ids:
        index = payload["dimension"][dim]["category"]["index"]
        dimensions[dim] = (
            [key for key, _ in sorted(index.items(), key=lambda pair: pair[1])]
            if isinstance(index, dict)
            else index
        )
    values = payload.get("value", {})
    flags = payload.get("status", {})
    if isinstance(values, list):
        values = {str(i): value for i, value in enumerate(values) if value is not None}
    if isinstance(flags, list):
        flags = {str(i): flag for i, flag in enumerate(flags) if flag}
    rows = []

    for flat_index in range(int(np.prod(sizes))):
        coords = np.unravel_index(flat_index, sizes)
        row = {dim: dimensions[dim][coord] for dim, coord in zip(ids, coords)}
        row.update(value=values.get(str(flat_index)), status_flag=flags.get(str(flat_index), ""))
        rows.append(row)
    frame = pd.DataFrame(rows)
    observed = frame["value"].dropna()
    assert observed.between(0, 100).all(), "Invalid percent in Eurostat input"
    assert not frame.duplicated(ids).any(), "Duplicate Eurostat dimension cell"
    return frame, payload


def country_iso3(code: str) -> str | None:
    country = pycountry.countries.get(alpha_2={"EL": "GR"}.get(code, code))
    return country.alpha_3 if country else None


def validate_sources(sources: pd.DataFrame) -> None:
    assert sources.source_id.is_unique, "Duplicate source ID"
    assert sources.source_url.str.startswith("https://").all(), "Missing source URL"
    assert sources.review_status.isin(["candidate", "source_documented", "data_extracted"]).all()
    for codes in sources.country_iso3:
        for code in codes.split(";"):
            if code and code != "AUTO":
                assert pycountry.countries.get(alpha_3=code), f"Invalid country code {code}"


def make_coverage(sources: pd.DataFrame, eu: pd.DataFrame) -> pd.DataFrame:

    baseline = eu[(eu.sex == "T") & (eu.age == "Y_GE16") & (eu.isced11 == "TOTAL")]
    eu_countries = sorted(
        {country_iso3(code) for code in baseline.loc[baseline.value.notna(), "geo"] if country_iso3(code)}
    )
    eu_scope = sorted({country_iso3(code) for code in baseline.geo if country_iso3(code)})
    sources.loc[sources.source_id == "eurostat", "country_iso3"] = ";".join(eu_scope)
    rows = []
    for country in sorted(pycountry.countries, key=lambda c: c.name):
        subset = sources[sources.country_iso3.map(lambda codes: country.alpha_3 in codes.split(";"))]
        statuses = set(subset.review_status)
        missing_eu = country.alpha_3 in eu_scope and country.alpha_3 not in eu_countries
        if missing_eu and not any(
            row.source_id != "eurostat" and row.review_status == "data_extracted"
            for row in subset.itertuples()
        ):
            statuses.discard("data_extracted")
        state = (
            "Data extracted"
            if "data_extracted" in statuses
            else "Public source documented"
            if "source_documented" in statuses
            else "Candidate only"
            if "candidate" in statuses
            else "Reviewed, missing result"
            if missing_eu
            else "Not researched"
        )

        def capability(col):
            return (
                "; ".join(
                    f"{row.source_id}: {'missing_total_population_result' if missing_eu and row.source_id == 'eurostat' and col == 'book_participation' else getattr(row, col)}"
                    for row in subset.itertuples()
                )
                or "unknown"
            )

        rows.append(
            dict(
                country_iso3=country.alpha_3,
                country=country.name,
                audit_status=state,
                source_ids=";".join(subset.source_id),
                book_participation=capability("book_participation"),
                audiobook_separate=capability("audiobook_separate"),
                genre_detail=capability("genre_detail"),
                research_gap=(
                    "Eurostat total-population result absent; retained as missing"
                    if missing_eu
                    else "No source reviewed in this audit"
                    if subset.empty
                    else ""
                ),
                note="ISO 3166 country/territory roster; not a list of sovereign states",
            )
        )
    result = pd.DataFrame(rows)
    assert result.country_iso3.is_unique
    assert len(result) == len(list(pycountry.countries))
    return result


def render_map(coverage: pd.DataFrame, reviewed_on: str) -> None:
    world = gpd.read_file(RAW / "world_boundaries.geojson")

    codes = world["ADM0_A3"].astype(str)
    valid = set(coverage.country_iso3)
    codes = codes.where(codes.isin(valid), world["ISO_A3_EH"].astype(str))
    world["country_iso3"] = codes
    world = world.merge(coverage[["country_iso3", "audit_status"]], on="country_iso3", how="left")
    world["audit_status"] = world.audit_status.fillna("Not researched")
    world = world[world["ADM0_A3"] != "ATA"].to_crs("ESRI:54030")
    fig, ax = plt.subplots(figsize=(14, 7.8))
    world.plot(ax=ax, color=world.audit_status.map(COLORS), edgecolor="white", linewidth=0.3)
    ax.set_axis_off()
    fig.suptitle("Global book-data source coverage", x=0.06, y=0.96, ha="left", fontsize=23, weight="bold")
    fig.text(
        0.06,
        0.91,
        f"Source audit reviewed {datetime.fromisoformat(reviewed_on).strftime('%d %B %Y')} • source readiness, not reading or listening rates",
        fontsize=12,
    )
    counts = coverage.audit_status.value_counts()
    ax.legend(
        handles=[Patch(facecolor=COLORS[s], label=f"{s} ({counts.get(s, 0)} entries)") for s in STATUS_ORDER],
        loc="lower center",
        bbox_to_anchor=(0.5, -0.06),
        ncol=2,
        frameon=False,
        fontsize=11,
    )
    fig.text(
        0.06,
        0.045,
        "Counts cover ISO countries and territories. Small territories may not appear at this map scale.\n"
        "Grey means no source reviewed, not no readers or no public data. Boundaries: Natural Earth; national scope needs review.",
        fontsize=10,
    )
    fig.subplots_adjust(left=0.03, right=0.97, top=0.86, bottom=0.15)
    fig.savefig(OUT / "coverage_map.png", dpi=160, facecolor="white")
    plt.close(fig)


def render_audit(sources: pd.DataFrame, coverage: pd.DataFrame, baseline: pd.DataFrame) -> None:
    counts = coverage.audit_status.value_counts()
    reviewed_date = datetime.fromisoformat(str(sources.reviewed_on.max())).strftime("%d %B %Y")
    rows = []
    for s in sources.itertuples():
        values = [
            s.title,
            s.country_iso3 or "Regional scope unbound",
            str(s.survey_year),
            s.review_status,
            s.population,
            s.recall_period,
            s.audiobook_separate,
            s.genre_detail,
            s.comparability_notes,
            s.next_action,
        ]
        cells = "".join(f"<td>{html.escape(value)}</td>" for value in values)
        rows.append(
            f'<tr>{cells}<td><a href="{html.escape(s.source_url, quote=True)}">Original source</a><br>'
            f"{html.escape(s.evidence_locator)}</td></tr>"
        )
    count_text = " · ".join(f"{state}: {counts.get(state, 0)}" for state in STATUS_ORDER)
    headers = [
        "Source",
        "Country codes",
        "Survey year",
        "Audit status",
        "Population",
        "Recall period",
        "Separate audio",
        "Genres",
        "Comparability limits",
        "Next action",
        "Evidence",
    ]
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Global Reading Atlas: source audit</title><style>
body{{font:16px/1.5 -apple-system,BlinkMacSystemFont,sans-serif;color:#253241;background:#f7f9fb;margin:0}}main{{max-width:1450px;margin:auto;padding:35px}}
h1{{font-size:34px}}p{{max-width:950px}}img{{width:100%;height:auto;background:white}}.scroll{{overflow:auto;background:white}}
table{{border-collapse:collapse;font-size:13px}}th,td{{padding:12px;text-align:left;vertical-align:top;border-bottom:1px solid #dde2e7;min-width:120px}}
th{{background:#eaf0f5}}a{{color:#245b85}}.note{{padding:16px;background:#fff2d6;border-left:4px solid #b78c36}}</style><main>
<h1>Global Reading Atlas</h1><p>Worldwide source register and evidence coverage. Reviewed {reviewed_date}.
Coverage reflects the reviewed material and remains incomplete. Source readiness does not measure reading levels.</p>
<p class="note">Separate audio and genre fields describe evidence availability. “Documented” does not mean the underlying estimates have been extracted or are comparable.
All missing observations remain missing. No cross-country format ranking is approved yet.</p>
<p>{html.escape(count_text)}. Roster: {len(coverage)} ISO countries and territories; {len(sources)} source families.</p>
<img src="coverage_map.png" alt="World map of source-audit readiness; exact country statuses are available in the coverage CSV below">
<h2>Files to use</h2><p><a href="../data/processed/coverage_matrix.csv">Full worldwide coverage matrix</a> ·
<a href="../data/processed/source_register.csv">Source register</a> ·
<a href="../data/processed/eurostat_baseline_2022.csv">Eurostat total-population baseline</a> ·
<a href="../data/raw/pew_formats.csv">Pew format extract</a></p>
<h2>Source register</h2><div class="scroll"><table><thead><tr>{"".join(f"<th>{h}</th>" for h in headers)}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<h2>What the audit supports</h2><p>Use Eurostat for its shared 2022 overall-book participation definition, which includes audio.
Use Pew for US format trends, preserving the 2025 survey-method break. Canada and Singapore now have checked format and genre profiles.
Daily Nordic use and annual participation belong in separate comparisons.</p>
<h2>Work still required</h2><p>Expand research in underrepresented regions and obtain comparable questions and eligible survey bases.
Canada’s original PDF resolves the reviewed webpage discrepancy; its exact genre subgroup sample sizes remain unpublished.
The Arab Reading Index remains a regional candidate until country sampling is checked.</p>
<p>Geographic boundaries use Natural Earth and do not express a position on borders. The CSV includes small territories missing from this map.</p>
</main></html>"""
    (OUT / "source_audit.html").write_text(page)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh Eurostat and map geometry; source metadata stays manually reviewed",
    )
    args = parser.parse_args(argv)
    for directory in [RAW, PROCESSED, OUT]:
        directory.mkdir(exist_ok=True, parents=True)
    downloads = []
    for url, filename in [
        (EUROSTAT_URL, "eurostat_ilc_scp27_2022.json"),
        (GEOMETRY_URL, "world_boundaries.geojson"),
    ]:
        path = RAW / filename
        if args.refresh or not path.exists():
            downloads.append(download(url, path))
    if downloads:
        (RAW / "download_receipt.json").write_text(json.dumps(downloads, indent=2))
    sources = pd.DataFrame(json.loads((ROOT / "data/source_register.json").read_text()))
    validate_sources(sources)
    eu, payload = eurostat_frame(RAW / "eurostat_ilc_scp27_2022.json")
    eu.to_csv(PROCESSED / "eurostat_all_cells_2022.csv", index=False)
    baseline = eu[(eu.sex == "T") & (eu.age == "Y_GE16") & (eu.isced11 == "TOTAL")].copy()
    baseline["country_iso3"] = baseline.geo.map(country_iso3)
    baseline["source_id"] = "eurostat"
    baseline["source_url"] = EUROSTAT_URL
    baseline.to_csv(PROCESSED / "eurostat_baseline_2022.csv", index=False)
    coverage = make_coverage(sources, eu)
    sources.to_csv(PROCESSED / "source_register.csv", index=False)
    coverage.to_csv(PROCESSED / "coverage_matrix.csv", index=False)

    pew = pd.read_csv(RAW / "pew_formats.csv")
    assert pew.value.between(0, 100).all()
    assert not pew.duplicated(["country_iso3", "survey_year", "format"]).any()
    assert set(pew.source_id).issubset(set(sources.source_id))
    render_map(coverage, str(sources.reviewed_on.max()))
    render_audit(sources, coverage, baseline)
    manifest = {
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "reviewed_on": str(sources.reviewed_on.max()),
        "python": platform.python_version(),
        "source_families": len(sources),
        "iso_entries": len(coverage),
        "coverage_counts": coverage.audit_status.value_counts().to_dict(),
        "eurostat_nonmissing_cells": int(eu.value.notna().sum()),
        "eurostat_updated": payload.get("updated"),
        "pew_observations": len(pew),
        "checks": "Percent ranges, dimension uniqueness, valid ISO codes, source references, complete roster",
        "input_hashes": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                RAW / "eurostat_ilc_scp27_2022.json",
                RAW / "world_boundaries.geojson",
                RAW / "pew_formats.csv",
                ROOT / "data/source_register.json",
            ]
        },
    }
    (OUT / "audit_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
