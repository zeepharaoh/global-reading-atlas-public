"""Check public releases, preserving reviewed data until new evidence is validated."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

from .audit import eurostat_frame
from .validation import reject_conflicting_definitions

ROOT = Path(__file__).resolve().parents[1]
EUROSTAT_HISTORY_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/ilc_scp27"
    "?lang=EN&sinceTimePeriod=2022"
)


def checked_source(source: dict, previous: dict, fetch=None) -> dict:
    """A failed check never overwrites a successful receipt or a reviewed observation."""
    row = dict(previous)
    row.update(
        source_id=source["source_id"],
        source_name=source["title"],
        latest_observation_year=source["survey_year"],
        update_method="Automatic API"
        if source["source_id"] == "eurostat"
        else "Check release; validate new extraction",
        last_checked_at=datetime.now(timezone.utc).isoformat(),
    )
    try:
        if fetch is None:
            request = Request(
                source["check_url"],
                headers={"User-Agent": "Mozilla/5.0 (Global Reading Atlas public-data checker)"},
            )
            with urlopen(request, timeout=25) as response:
                content = response.read()
        else:
            content = fetch(source["check_url"])
        digest = hashlib.sha256(content).hexdigest()
        if source["source_id"] == "eurostat":
            folder = ROOT / "work/updates"
            folder.mkdir(parents=True, exist_ok=True)
            candidate = folder / "eurostat-candidate.json"
            candidate.write_bytes(content)
            frame, _ = eurostat_frame(candidate)
            required = {"geo", "sex", "age", "isced11", "unit", "n_book", "time", "value"}
            if not required.issubset(frame.columns) or frame.value.notna().sum() == 0:
                raise ValueError("Eurostat schema or observed values missing")
            years = pd.to_numeric(frame.time).astype(int)
            if not years.between(2022, datetime.now(timezone.utc).year).all():
                raise ValueError("Unexpected survey year")
            raw = ROOT / "data/raw/eurostat_ilc_scp27_since2022.json"
            raw.write_bytes(content)
            row["latest_observation_year"] = int(years.max())
            row["status"] = "API refreshed and validated"
            row["notes"] = (
                "All available survey waves from 2022. Missing years stay missing. Includes audio without a separate listening measure."
            )
        else:
            changed = previous.get("sha256") not in {None, digest}

            pending = changed or previous.get("review_pending", False)
            row["review_pending"] = pending
            row["status"] = (
                "Changed source; extraction review needed"
                if pending
                else "Source checked; reviewed data retained"
            )
            row["notes"] = (
                "A source change may be page layout or a new report. It does not automatically create a new survey observation."
            )
        row.update(sha256=digest, check_url=source["check_url"], last_success_at=row["last_checked_at"])
        row.pop("error", None)
    except Exception as exc:
        row.update(
            status="Check failed; last reviewed data retained", notes=str(exc), error=type(exc).__name__
        )
    return row


def check_sources() -> list[dict]:
    state_path = ROOT / "data/raw/source_check_state.json"
    previous = json.loads(state_path.read_text()) if state_path.exists() else []
    previous = {row["source_id"]: row for row in previous}
    sources = json.loads((ROOT / "data/source_register.json").read_text())
    sources = [source for source in sources if source["review_status"] == "data_extracted"]
    landing_pages = {
        "eurostat": EUROSTAT_HISTORY_URL,
        "nordicom_se": "https://www.nordicom.gu.se/sv/fakta-analys/mediebarometern",
        "ssb_no": "https://www.ssb.no/kultur-og-fritid/tids-og-mediebruk/statistikk/norsk-mediebarometer",
        "booknet_ca": "https://booknetcanada.ca/research-archive/",
        "storytel_story_report_2026": "https://www.storytelgroup.com/en/newsroom/",
    }
    for source in sources:
        source["check_url"] = landing_pages.get(source["source_id"], source["source_url"])
    company_path = ROOT / "data/curated/company_register.csv"
    if company_path.exists():
        for company in pd.read_csv(company_path).to_dict("records"):
            sources.append(
                {
                    "source_id": f"company:{company['company_id']}",
                    "title": company["company"],
                    "survey_year": None,
                    "check_url": company["source_url"],
                }
            )
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(
            pool.map(lambda source: checked_source(source, previous.get(source["source_id"], {})), sources)
        )


    try:
        ssb_receipt = refresh_ssb_formats()
        for row in rows:
            if row["source_id"] == "ssb_no":
                row["api_sha256"] = ssb_receipt["sha256"]
                row["update_method"] = "Automatic print/ebook API; audiobook release review"
                row["notes"] += (
                    " Paper and ebook table 11556 refreshed and validated separately; no broader audio-media proxy imported."
                )
    except Exception as exc:
        for row in rows:
            if row["source_id"] == "ssb_no":
                row["status"] = "Partial check; print/ebook API failed"
                row["notes"] += f" API: {exc}. Last reviewed data retained."
    state_path.write_text(json.dumps(rows, indent=2) + "\n")
    folder = ROOT / "outputs"
    folder.mkdir(exist_ok=True)
    (folder / "refresh_status.json").write_text(json.dumps(rows, indent=2) + "\n")
    return rows


def refresh_ssb_formats() -> dict:
    url = "https://data.ssb.no/api/v0/en/table/11556"
    headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
    with urlopen(Request(url, headers=headers), timeout=25) as response:
        metadata = json.load(response)
    dimensions = {variable["code"]: variable for variable in metadata["variables"]}
    if not {"01", "25"}.issubset(dimensions["Media"]["values"]):
        raise ValueError("SSB paper/ebook codes changed")
    years = [
        year for year in dimensions["Tid"]["values"] if 2022 <= int(year) <= datetime.now(timezone.utc).year
    ]
    payload = {
        "query": [
            {"code": "Media", "selection": {"filter": "item", "values": ["01", "25"]}},
            {"code": "ContentsCode", "selection": {"filter": "item", "values": ["AndelBrukere"]}},
            {"code": "Tid", "selection": {"filter": "item", "values": years}},
        ],
        "response": {"format": "json-stat2"},
    }
    with urlopen(Request(url, data=json.dumps(payload).encode(), headers=headers), timeout=25) as response:
        content = response.read()
    candidate = ROOT / "work/updates/ssb-candidate.json"
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_bytes(content)
    parsed = ssb_format_rows(candidate)
    reviewed = pd.read_csv(ROOT / "data/curated/format_history_nordics.csv")
    compared = parsed.merge(
        reviewed[reviewed.country_iso3.eq("NOR") & reviewed.format_label.isin(["Print", "Ebook"])],
        on=["year", "format_label"],
        suffixes=("_api", "_reviewed"),
    )
    reviewed_keys = reviewed[reviewed.country_iso3.eq("NOR") & reviewed.format_label.isin(["Print", "Ebook"])]
    if (
        len(compared) != len(reviewed_keys)
        or not (compared.participation_api == compared.participation_reviewed).all()
    ):
        raise ValueError("SSB API disagrees with reviewed report values")
    target = ROOT / "data/raw/ssb_formats_since2022.json"
    target.write_bytes(content)
    return {
        "url": url,
        "sha256": hashlib.sha256(content).hexdigest(),
        "file": str(target.relative_to(ROOT)),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def ssb_format_rows(path: Path) -> pd.DataFrame:
    frame, payload = eurostat_frame(path)
    if set(payload["id"]) != {"Media", "ContentsCode", "Tid"}:
        raise ValueError("SSB response includes an unreviewed population dimension")
    if not {"Media", "ContentsCode", "Tid", "value"}.issubset(frame.columns) or set(frame.ContentsCode) != {
        "AndelBrukere"
    }:
        raise ValueError("SSB percentage schema changed")
    labels = payload["dimension"]["Media"]["category"]["label"]
    if labels.get("01") != "Book" or labels.get("25") != "Electronic book":
        raise ValueError("SSB format definitions changed")
    result = pd.DataFrame(
        {
            "year": frame.Tid.astype(int),
            "format_label": frame.Media.map({"01": "Print", "25": "Ebook"}),
            "participation": frame.value,
        }
    )
    if result.duplicated(["year", "format_label"]).any():
        raise ValueError("Duplicate SSB format/year observation")
    if not result.year.between(2022, datetime.now(timezone.utc).year).all():
        raise ValueError("SSB response outside the requested period")
    if result.participation.dropna().empty or not result.participation.dropna().between(0, 100).all():
        raise ValueError("SSB percentage outside [0, 100]")
    if result.format_label.isna().any():
        raise ValueError("Unexpected media measure")
    result = result.assign(
        country_iso3="NOR",
        country="Norway",
        denominator="Population age 9+",
        population="Norwegian population age 9+",
        period="Average day",
        comparison_group="Daily population reach",
        source_id="ssb_no",
        source_url="https://www.ssb.no/en/statbank/table/11556",
        evidence_locator="Table 11556; Media=01 or 25; ContentsCode=AndelBrukere; Tid=year",
        sample_size=float("nan"),
        notes="SSB paper/ebook API; 2022 onward population age 9+, daily reach. Audiobooks come from a separate reviewed question; formats overlap.",
    )
    return result


def freshness(sources: pd.DataFrame) -> pd.DataFrame:
    state_path = ROOT / "data/raw/source_check_state.json"
    checked = (
        {row["source_id"]: row for row in json.loads(state_path.read_text())} if state_path.exists() else {}
    )
    rows = []
    for source in sources[sources.review_status == "data_extracted"].to_dict("records"):
        row = checked.get(source["source_id"], {})
        rows.append(
            {
                "source_id": source["source_id"],
                "source_name": source["title"],
                "latest_observation_year": max(
                    int(row.get("latest_observation_year", source["survey_year"])), int(source["survey_year"])
                ),
                "last_checked_at": row.get("last_checked_at", source.get("reviewed_on", "")),
                "status": row.get("status", "Reviewed extraction; automated check not yet run"),
                "update_method": row.get("update_method", "Check release; validate new extraction"),
                "notes": row.get("notes", source["comparability_notes"]),
            }
        )
    company_path = ROOT / "data/curated/company_register.csv"
    if company_path.exists():
        for company in pd.read_csv(company_path).to_dict("records"):
            source_id = f"company:{company['company_id']}"
            row = checked.get(source_id, {})
            rows.append(
                {
                    "source_id": source_id,
                    "source_name": company["company"],
                    "latest_observation_year": None,
                    "last_checked_at": row.get("last_checked_at", company["reviewed_on"]),
                    "status": row.get("status", "Reviewed inventory; automated check not yet run"),
                    "update_method": "Check company source; validate new reporting",
                    "notes": "Company/service inventory; no quantitative observation year. "
                    + row.get("notes", company["notes"]),
                }
            )
    return pd.DataFrame(rows)


def history(profiles: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "country_iso3",
        "country",
        "year",
        "participation",
        "denominator",
        "population",
        "period",
        "comparison_group",
        "source_id",
        "source_url",
        "evidence_locator",
        "notes",
    ]
    rows = profiles[profiles.format_label == "Audiobook"][columns].copy()
    extra = ROOT / "data/curated/audiobook_history_extra.csv"
    if extra.exists():
        rows = pd.concat([rows, pd.read_csv(extra)[columns]], ignore_index=True)
    rows = rows[rows.year.between(2022, datetime.now(timezone.utc).year)]
    keys = ["country_iso3", "year", "comparison_group"]

    reject_conflicting_definitions(rows, keys)
    rows = rows.drop_duplicates(keys, keep="last")
    if not rows.participation.dropna().between(0, 100).all():
        raise ValueError("Invalid audiobook history percentage")
    return rows.sort_values(["country_iso3", "comparison_group", "year"])
