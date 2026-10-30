"""Explore the reviewed Global Reading Atlas snapshot with Streamlit."""

from datetime import date
import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from src.coverage_map import coverage_map_features
from src.streamlit_data import load_snapshot, query_frame, select_rows, source_detail


ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "data/processed/dashboard_snapshot.json"
PAGES = ["Audiobooks", "Industry", "Reading", "Formats", "Genres", "Coverage", "Reports"]
REPORTS = {
    "Audiobook market analysis": ("outputs/audiobook_notebook.html", "notebooks/02_audiobook_market_check.ipynb"),
    "Reading and listening analysis": ("outputs/notebook.html", "notebooks/01_reading_and_listening_analysis.ipynb"),
}
FORMAT_COLORS = {"Print": "#25658c", "Ebook": "#a98026", "Audiobook": "#d36b3d"}
COVERAGE_COLORS = {
    "Data extracted": "#25897e", "Reviewed, missing result": "#c68038",
    "Public source documented": "#6285b0", "Candidate only": "#b39a64", "Not researched": "#dde3e7",
}
LABELS = {
    "country_iso3": "Country code", "participation": "Reported percentage", "year": "Observation year",
    "source_url": "Original source", "evidence_locator": "Exact table or page",
    "denominator": "Survey base", "population": "Reference population", "period": "Recall period",
    "comparison_group": "Measure family", "format_label": "Format", "source_id": "Source ID",
    "publication_date": "Publication date", "reviewed_at": "Footprint review date",
    "group_presence": "Group presence", "brand_presence": "Brand presence",
    "latest_observation_year": "Latest observation year", "last_checked_at": "Last source check",
}


@st.cache_data(show_spinner=False)
def read_reviewed_snapshot(path: str, modified: int, size: int) -> dict:
    return load_snapshot(path)


@st.cache_data(show_spinner=False)
def read_map_geometry(path: str, modified: int, size: int) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def coverage_map_chart(coverage):
    geometry_path = ROOT / "data/raw/world_boundaries.geojson"
    info = geometry_path.stat()
    raw = read_map_geometry(str(geometry_path), info.st_mtime_ns, info.st_size)
    geometry = {
        "type": "FeatureCollection",
        "features": [feature for feature in raw["features"] if feature["properties"].get("ADM0_A3") != "ATA"],
    }
    context = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": feature["geometry"], "properties": {}}
                     for feature in geometry["features"]],
    }
    selected = coverage_map_features(coverage, geometry)
    data_format = alt.DataFormat(property="features", type="json")
    background = alt.Chart(alt.InlineData(values=context, format=data_format)).mark_geoshape(
        fill="#f4f6f8", stroke="#aab4be", strokeWidth=0.35,
    )
    foreground = alt.Chart(alt.InlineData(values=selected, format=data_format)).mark_geoshape(
        stroke="white", strokeWidth=0.4,
    ).encode(
        color=alt.Color(
            "properties.audit_status:N", title="Source review status",
            scale=alt.Scale(domain=list(COVERAGE_COLORS), range=list(COVERAGE_COLORS.values())),
            legend=alt.Legend(orient="bottom", columns=2, labelLimit=260),
        ),
        tooltip=[
            alt.Tooltip("properties.country:N", title="Country or territory"),
            alt.Tooltip("properties.audit_status:N", title="Source review status"),
            alt.Tooltip("properties.book_participation:N", title="Book participation evidence"),
            alt.Tooltip("properties.audiobook_separate:N", title="Audiobook evidence"),
            alt.Tooltip("properties.genre_detail:N", title="Genre evidence"),
            alt.Tooltip("properties.research_gap:N", title="Remaining research gap"),
        ],
    )
    st.altair_chart(
        (background + foreground).project(type="equalEarth").properties(height=400),
        width="stretch", key="coverage_map",
    )
    st.caption("Colours show source review status. Hover over a coloured country for its evidence details. Neutral outlines provide geographic context outside the selected status.")
    st.caption("Natural Earth boundaries are simplified and small territories may be absent at this scale. The complete country and territory roster remains in the table below.")


def label(column):
    return LABELS.get(column, column.replace("_", " ").capitalize())


def reset_filters():
    for key in list(st.session_state):
        if key != "atlas_page":
            del st.session_state[key]


def within_years(frame, years):
    return frame.loc[frame.year.between(*years)].copy()


def choose(title, values, key, preferred=None):
    options = sorted(pd.Series(values).dropna().unique().tolist())
    if not options:
        return None
    index = options.index(preferred) if preferred in options else 0
    return st.selectbox(title, options, index=index, key=key)


def evidence(snapshot, query_id, rows, key):
    with st.expander("Source data and definitions"):
        st.caption(source_detail(snapshot, query_id).get("label", "Reviewed evidence"))
        shown = rows.rename(columns=label)
        st.dataframe(
            shown, hide_index=True, width="stretch", key=f"{key}_data",
            column_config={"Original source": st.column_config.LinkColumn(display_text="Open source")},
        )
        st.download_button(
            "Download these rows", rows.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"atlas_{query_id}.csv", mime="text/csv", key=f"{key}_download",
        )
        st.json({
            "source": source_detail(snapshot, query_id),
            "methods": snapshot["queries"][query_id]["methods"],
        }, expanded=False)
        if "source_id" in rows:
            checks = select_rows(query_frame(snapshot, "data_freshness"), {
                "source_id": rows.source_id.dropna().unique().tolist(),
            })
            if not checks.empty:
                st.caption("Observation years and source check dates describe different things.")
                st.dataframe(checks.rename(columns=label), hide_index=True, width="stretch")


def observation_status(snapshot, available, years, value_column="participation"):
    observed = available.loc[available[value_column].notna()] if value_column in available else available
    if observed.empty:
        st.caption("No reviewed observation is available for this survey profile.")
        return
    latest = int(observed.year.max())
    parts = [f"Latest available observation: {latest}"]
    if "source_id" in available:
        checks = select_rows(query_frame(snapshot, "data_freshness"), {
            "source_id": available.source_id.dropna().unique().tolist(),
        })
        checked = pd.to_datetime(checks.last_checked_at, format="mixed", errors="coerce", utc=True).max()
        if pd.notna(checked):
            parts.append("Latest source check: " + checked.strftime("%d %B %Y") + " (UTC)")
    st.caption(" · ".join(parts))
    if years[1] not in set(observed.year.astype(int)):
        st.info(f"No reviewed observation for {years[1]} in this selection. Missing years are not estimated.")


def population_note(rows):
    if rows.empty:
        return
    parts = []
    for column in ["denominator", "population", "period"]:
        if column in rows:
            values = rows[column].dropna().unique().tolist()
            parts.append(f"{label(column)}: " + "; ".join(str(value) for value in values))
    st.caption(" · ".join(parts))


def percentages(rows, category, key, group=None):
    observed = rows.loc[rows.participation.notna()].copy()
    if observed.empty:
        st.info("No verified percentage is available for this selection.")
        return
    encoding = {
        "x": alt.X("participation:Q", title="Reported percentage", scale=alt.Scale(domain=[0, 100])),
        "y": alt.Y(f"{category}:N", title=None, sort="-x", axis=alt.Axis(labelLimit=220, labelOverlap=False)),
        "tooltip": [alt.Tooltip(f"{category}:N", title=label(category)),
                    alt.Tooltip("participation:Q", title="Percent", format=".1f")],
    }
    if group:
        groups = sorted(observed[group].unique())
        encoding.update({
            "yOffset": alt.YOffset(f"{group}:N"),
            "color": alt.Color(f"{group}:N", title=label(group), scale=alt.Scale(
                domain=groups, range=[FORMAT_COLORS.get(value, "#25658c") for value in groups],
            )),
        })
        encoding["tooltip"].append(alt.Tooltip(f"{group}:N", title=label(group)))
    else:
        encoding["color"] = alt.value("#25658c")
    height = max(200, min(1000, 25 * len(observed)))
    chart = alt.Chart(observed).mark_bar(cornerRadiusEnd=3).encode(**encoding).properties(height=height)
    st.altair_chart(chart, width="stretch", key=key)
    missing = rows.loc[rows.participation.isna()]
    if not missing.empty:
        st.caption("Unavailable observations stay missing: " + "; ".join(missing[category].astype(str).unique()))


def history_chart(rows, years, key, group=None):
    observed = rows.loc[rows.participation.notna()].copy()
    if observed.empty:
        st.info("No verified observations in the selected years. Unpublished years are not estimated.")
        return
    encoding = {
        "x": alt.X("year:Q", title="Observation year", scale=alt.Scale(
            domain=[years[0] - 0.25, years[1] + 0.25], nice=False,
        ), axis=alt.Axis(values=list(range(years[0], years[1] + 1)), format="d")),
        "y": alt.Y("participation:Q", title="Reported percentage", scale=alt.Scale(domain=[0, 100])),
        "tooltip": [alt.Tooltip("year:Q", title="Observation year", format="d"),
                    alt.Tooltip("participation:Q", title="Percent", format=".1f"),
                    alt.Tooltip("denominator:N", title="Survey base"),
                    alt.Tooltip("period:N", title="Recall period")],
    }
    if group:
        groups = sorted(observed[group].unique())
        encoding["color"] = alt.Color(f"{group}:N", title=label(group), scale=alt.Scale(
            domain=groups, range=[FORMAT_COLORS.get(value, "#25658c") for value in groups],
        ))
        encoding["tooltip"].append(alt.Tooltip(f"{group}:N", title=label(group)))
    else:
        encoding["color"] = alt.value("#d36b3d")
    st.altair_chart(
        alt.Chart(observed).mark_circle(size=130).encode(**encoding).properties(height=280),
        width="stretch", key=key,
    )
    st.caption("Points represent published observations. Gaps are retained; no annual values or growth are inferred.")


def audiobook_page(snapshot, years):
    st.title("Audiobooks")
    history = query_frame(snapshot, "audiobook_history")
    left, right = st.columns(2)
    with left:
        country = choose("Country", history.country, "audio_country", "Sweden")
    country_rows = select_rows(history, {"country": country})
    with right:
        measure = choose("Measure family", country_rows.comparison_group, "audio_measure")
    available = select_rows(country_rows, {"comparison_group": measure})
    rows = within_years(available, years)
    st.subheader("Observed audiobook use")
    observation_status(snapshot, available, years)
    population_note(available)
    if not rows.empty:
        latest = rows.sort_values("year").iloc[-1]
        left, right = st.columns(2)
        left.metric("Latest reported percentage", f"{latest.participation:.1f}%")
        right.metric("Latest observation year", str(int(latest.year)))
    history_chart(rows, years, "audio_history")
    st.caption("National participation, daily reach and reader subsets have different bases. No country ranking is made.")
    evidence(snapshot, "audiobook_history", rows, "audio_history")

    st.subheader("Genres and listening moments among listeners")
    st.caption("Separate 2026 survey commissioned by Storytel. These results describe audiobook listeners, not national reach or Storytel customers.")
    listener = query_frame(snapshot, "storytel_audio_2026")
    left, right = st.columns(2)
    with left:
        listener_country = choose("Listener study country", listener.country, "listener_country", "Sweden")
    with right:
        kind = st.selectbox("Listener question", ["Genres", "Listening moments"], key="listener_kind")
    available = select_rows(listener, {
        "country": listener_country, "record_type": "genre" if kind == "Genres" else "moment",
    })
    selected = within_years(available, years)
    observation_status(snapshot, available, years)
    population_note(available)
    percentages(selected, "item", "listener_results")
    st.caption("Only each country's five published options are available. Unlisted options are unreported, and multiple answers can overlap.")
    evidence(snapshot, "storytel_audio_2026", selected, "listener_results")


def industry_page(snapshot, years):
    st.title("Book industry")
    industry = query_frame(snapshot, "industry_metrics")
    countries = sorted(industry.country.unique())
    st.caption("Published book industry money figures include publisher revenue, retail turnover and other reported sales values. Audience measures are in Audiobooks and Reading.")
    st.caption(f"Reviewed monetary evidence covers {len(countries)} countries. Worldwide coverage is incomplete. The company list below has a separate reporting scope.")
    country = choose("Country", countries, "industry_country", "United States")
    names = select_rows(industry, {"country": country}).drop_duplicates("series_id").set_index("series_id")
    series_options = names.index.tolist()
    preferred = next((value for value in series_options if "audio" in names.loc[value, "metric"].lower()), series_options[0])
    if st.session_state.get("industry_series") not in series_options:
        st.session_state["industry_series"] = preferred
    series = st.selectbox("Revenue measure", series_options, index=series_options.index(preferred),
                          key="industry_series", format_func=lambda value: names.loc[value, "metric"])
    st.subheader(f"{country}: {names.loc[series, 'metric']}")
    available = select_rows(industry, {"series_id": series})
    rows = within_years(available, years)
    observation_status(snapshot, available, years, "value")
    st.caption(names.loc[series, "scope"])
    st.caption("Unit: " + names.loc[series, "unit"])
    if rows.empty:
        st.info("No published observations in the selected years.")
    else:
        st.altair_chart(alt.Chart(rows).mark_bar(color="#25658c", cornerRadiusEnd=3).encode(
            x=alt.X("year:O", title="Observation year", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("value:Q", title=names.loc[series, "unit"], scale=alt.Scale(zero=True)),
            tooltip=[alt.Tooltip("year:O", title="Observation year"), "value:Q", "unit:N", "publication_date:N"],
        ).properties(height=340), width="stretch", key="industry_history")
    st.caption("Each chart keeps one source definition and currency. Publisher receipts, retail turnover and operating revenue measure different parts of the market. These values cannot form a country ranking. Report vintages and unpublished years remain visible.")
    evidence(snapshot, "industry_metrics", rows, "industry")

    st.subheader("Company and service register")
    companies = query_frame(snapshot, "companies")
    book_format = st.selectbox("Format in company register", ["All", "Print", "Ebook", "Audiobook"],
                               key="company_format")
    if book_format != "All":
        companies = companies.loc[companies.formats.str.contains(book_format, regex=False, na=False)].copy()
    st.caption("The reviewed register covers 23 companies and services. It is not a complete worldwide census. Parent and brand rows overlap; company totals are not audiobook totals.")
    st.dataframe(companies.rename(columns=label), hide_index=True, width="stretch",
                 column_config={"Original source": st.column_config.LinkColumn(display_text="Open source")})
    evidence(snapshot, "companies", companies, "companies")


def reading_page(snapshot, years):
    st.title("Book participation")
    st.caption("Comparable Eurostat 2022 observations among people aged 16 and over. The measure includes paper books, ebooks and audiobooks.")
    baseline = query_frame(snapshot, "europe")
    scope = st.selectbox("Geography", ["All surveyed countries", "EU members", "Other surveyed countries"],
                         key="reading_geography")
    if scope != "All surveyed countries":
        baseline = baseline.loc[baseline.scope.eq("EU member") if scope == "EU members" else ~baseline.scope.eq("EU member")]
    countries = st.multiselect("Countries (empty means all)", sorted(baseline.country.unique()), key="reading_countries")
    if countries:
        baseline = select_rows(baseline, {"country": countries})
    rows = within_years(baseline, years)
    observation_status(snapshot, baseline, years)
    percentages(rows, "country", "reading_countries_chart")
    if years[0] <= 2022 <= years[1]:
        benchmark = query_frame(snapshot, "eu_benchmark").iloc[0]
        st.caption(f"Published EU27 aggregate: {benchmark.participation:.1f}%. This is the official aggregate, not a mean of the selected countries.")
    evidence(snapshot, "europe", rows, "reading")

    st.subheader("Within country demographic profiles")
    demographics = query_frame(snapshot, "demographics")
    country = choose("Demographic country", demographics.country, "demographic_country", "Sweden")
    dimension = st.selectbox("Demographic group", ["Age", "Sex", "Education"], key="demographic_dimension")
    selected = within_years(select_rows(demographics, {"country": country}), years)
    if dimension == "Age":
        selected = selected.loc[selected.sex.eq("T") & selected.isced11.eq("TOTAL") & ~selected.age.eq("Y_GE16")]
        category = "age_label"
    elif dimension == "Sex":
        selected = selected.loc[selected.age.eq("Y_GE16") & selected.isced11.eq("TOTAL") & ~selected.sex.eq("T")]
        category = "sex_label"
    else:
        selected = selected.loc[selected.sex.eq("T") & selected.age.eq("Y_GE16") & ~selected.isced11.eq("TOTAL")]
        category = "education_label"
    percentages(selected, category, "demographic_chart")
    st.caption("Each group uses its own population base. Differences describe associations; unavailable or unreliable values remain missing.")
    evidence(snapshot, "demographics", selected, "demographics")


def formats_page(snapshot, years):
    st.title("Paper books, ebooks and audiobooks")
    history = query_frame(snapshot, "format_history")
    country = choose("Country", history.country, "formats_country", "Sweden")
    country_rows = select_rows(history, {"country": country})
    rows = within_years(country_rows, years)
    st.subheader("Observed format use by year")
    observation_status(snapshot, country_rows, years)
    population_note(country_rows)
    history_chart(rows, years, "format_history", "format_label")
    st.caption("Formats overlap and are never added together. Annual reader panels and daily population reach remain separate country profiles.")
    evidence(snapshot, "format_history", rows, "format_history")
    year = choose("Profile year", rows.year if not rows.empty else [], "format_profile_year",
                  int(rows.year.max()) if not rows.empty else None)
    if year is not None:
        profile = select_rows(rows, {"year": year})
        st.subheader("Selected survey profile")
        percentages(profile, "format_label", "format_profile")
        evidence(snapshot, "format_history", profile, "format_profile")


def genres_page(snapshot, years):
    st.title("Genres")
    studies = {
        "genre_history": query_frame(snapshot, "genre_history"),
        "storytel_audio_2026": select_rows(
            query_frame(snapshot, "storytel_audio_2026"), {"record_type": "genre"},
        ),
    }
    country_sources = pd.concat([
        frame[["country", "source_id"]].assign(query_id=query_id)
        for query_id, frame in studies.items()
    ], ignore_index=True).drop_duplicates()
    st.caption(f"Reviewed genre evidence covers {country_sources.country.nunique()} countries. Every available country is in the list below.")
    st.caption("Choose a country, then its source, question, format and observation year. Survey populations and questions remain separate.")
    country = choose("Country", country_sources.country, "genres_country", "Canada")
    country_studies = select_rows(country_sources, {"country": country})
    registered = query_frame(snapshot, "sources")
    source_names = registered.set_index("source_id").title.to_dict()
    source = st.selectbox(
        "Survey source", sorted(country_studies.source_id.unique()),
        format_func=lambda value: source_names.get(value, value), key="genres_source",
    )
    selected_studies = select_rows(country_studies, {"source_id": source})
    query_id = selected_studies.query_id.iloc[0]
    country_rows = select_rows(studies[query_id], {"country": country, "source_id": source})
    genre_scope = choose("Genre question", country_rows.genre_scope, "genres_scope", "Book fiction genres")
    available = select_rows(country_rows, {"genre_scope": genre_scope})
    choices = ["All formats", *sorted(available.format_label.unique())]
    preferred = choices.index("Audiobook") if "Audiobook" in choices else 0
    book_format = st.selectbox("Format", choices, index=preferred, key="genres_format")
    if book_format != "All formats":
        available = select_rows(available, {"format_label": book_format})
    if query_id == "storytel_audio_2026":
        st.caption("Commissioned by Storytel and conducted by Trackit Insight in April 2026. Results describe audiobook listeners, not national reach or Storytel customers.")
        st.caption("Only the five published genres in each country are available. Multiple answers can overlap. Unlisted genres are unreported, not zero.")
    observation_status(snapshot, available, years)
    rows = within_years(available, years)
    if rows.empty:
        population_note(available)
        evidence(snapshot, query_id, rows, "genres")
        return
    year = choose("Chart observation year", rows.year, "genres_year", int(rows.year.max()))
    rows = select_rows(rows, {"year": year})
    population_note(rows)
    st.caption("Genre questions can allow multiple answers, so percentages are not market shares and do not sum to 100%. Each format can have a different reader base.")
    if country == "Singapore":
        st.info("Singapore's question includes websites, social media and magazines. It is a mixed material reading question, not an audiobook genre measure.")
    percentages(rows, "genre", "genre_chart", "format_label" if book_format == "All formats" else None)
    evidence(snapshot, query_id, rows, "genres")


def coverage_page(snapshot, years):
    st.title("Evidence coverage")
    coverage = query_frame(snapshot, "coverage")
    st.caption("249 countries and territories form the research roster. Audit status describes reviewed coverage, not reading levels or proof that no public data exists.")
    status = st.selectbox("Audit status", ["All", *sorted(coverage.audit_status.unique())], key="coverage_status_filter")
    if status != "All":
        coverage = select_rows(coverage, {"audit_status": status})
    st.subheader("World map of evidence coverage")
    coverage_map_chart(coverage)
    counts = coverage.groupby("audit_status", as_index=False).size().rename(columns={"size": "countries"})
    st.altair_chart(alt.Chart(counts).mark_bar(color="#25658c").encode(
        x=alt.X("countries:Q", title="Countries and territories"),
        y=alt.Y("audit_status:N", title=None, axis=alt.Axis(labelLimit=250)),
        tooltip=["audit_status:N", "countries:Q"],
    ).properties(height=220), width="stretch", key="coverage_status")
    st.dataframe(coverage.rename(columns=label), hide_index=True, width="stretch")
    evidence(snapshot, "coverage", coverage, "coverage")
    st.subheader("Source checks and observation years")
    freshness = query_frame(snapshot, "data_freshness")
    st.dataframe(freshness.rename(columns=label), hide_index=True, width="stretch")
    st.caption("A recent source check does not create a new survey observation. Retrieval failures preserve the last validated data.")
    st.subheader("Source register")
    sources = query_frame(snapshot, "sources")
    st.dataframe(sources.rename(columns=label), hide_index=True, width="stretch",
                 column_config={"Original source": st.column_config.LinkColumn(display_text="Open source")})
    evidence(snapshot, "sources", sources, "sources")


def reports_page(snapshot, years):
    st.title("Analysis reports")
    selected = st.selectbox("Report", list(REPORTS), key="report_choice")
    st.caption("These saved analyses use the full reviewed dataset. Dashboard filters do not change their results.")
    report_name, notebook_name = REPORTS[selected]
    report_path = ROOT / report_name
    notebook_path = ROOT / notebook_name
    try:
        report_html = report_path.read_text(encoding="utf-8")
    except OSError:
        st.error("This report is unavailable. Choose another report from the list above.")
        return
    report_column, notebook_column = st.columns(2)
    with report_column:
        st.download_button(
            "Download report", report_html.encode("utf-8"), file_name=report_path.name,
            mime="text/html", key="report_html_download",
        )
    with notebook_column:
        if notebook_path.is_file():
            st.download_button(
                "Download notebook (.ipynb)", notebook_path.read_bytes(), file_name=notebook_path.name,
                mime="application/x-ipynb+json", key="report_notebook_download",
            )
        else:
            st.caption("The notebook download is unavailable.")
    st.iframe(report_html, height=900, tab_index=0, alt=f"{selected} report")


def main():
    st.set_page_config(page_title="Global Reading Atlas", page_icon="📚", layout="wide")
    try:
        info = SNAPSHOT.stat()
        snapshot = read_reviewed_snapshot(str(SNAPSHOT), info.st_mtime_ns, info.st_size)
    except (OSError, ValueError, KeyError):
        st.error("The reviewed snapshot is missing or invalid. Prepare and validate the project data before starting the app.")
        st.stop()
    st.sidebar.title("Global Reading Atlas")
    page = st.sidebar.radio("Explore", PAGES, key="atlas_page")
    years = (2022, max(2026, date.today().year))
    if page not in {"Coverage", "Reports"}:
        years = st.sidebar.slider("Observation years", 2022, years[1], years, key="atlas_years")
    st.sidebar.button("Reset filters", on_click=reset_filters)
    checked = pd.to_datetime(query_frame(snapshot, "data_freshness").last_checked_at,
                             format="mixed", errors="coerce", utc=True).max()
    if pd.notna(checked):
        st.sidebar.caption("Latest recorded source check: " + checked.strftime("%d %B %Y") + " (UTC)")
    st.sidebar.link_button("Source code on GitHub", "https://github.com/zeepharaoh/global-reading-atlas-public")
    {
        "Audiobooks": audiobook_page, "Industry": industry_page, "Reading": reading_page,
        "Formats": formats_page, "Genres": genres_page, "Coverage": coverage_page, "Reports": reports_page,
    }[page](snapshot, years)


if __name__ == "__main__":
    main()
