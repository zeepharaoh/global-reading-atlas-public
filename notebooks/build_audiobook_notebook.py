"""Build the audiobook market notebook from the dashboard's cached data.

Run `.venv/bin/python notebooks/build_audiobook_notebook.py` from the project root.
Use --no-execute to create a draft; otherwise execute and retain every cell output.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import textwrap
from pathlib import Path

import nbformat
import pandas as pd
from jupyter_client import KernelManager
from nbclient import NotebookClient
from portable_html import export_notebook_html


def cell(kind: str, text: str):
    cleaned = textwrap.dedent(text).strip()
    result = (nbformat.v4.new_markdown_cell if kind == "markdown" else nbformat.v4.new_code_cell)(cleaned)
    result.id = hashlib.sha256((kind + cleaned).encode()).hexdigest()[:12]
    return result


def md(text: str):
    return cell("markdown", text)


def code(text: str):
    return cell("code", text)


def make_notebook(project_root: Path):
    formats = pd.read_csv(project_root / "data/processed/format_profiles.csv")
    audio_path = project_root / "data/processed/audiobook_evidence.csv"
    audio = pd.read_csv(audio_path) if audio_path.is_file() else formats[formats.format_label.eq("Audiobook")]
    us = pd.read_csv(project_root / "data/processed/us_formats.csv")
    audio_us = us[us.format_label.eq("Audiobook")].set_index("year")
    genres = pd.read_csv(project_root / "data/processed/genre_profiles.csv")
    genre_history_path = project_root / "data/processed/genre_history.csv"
    genre_history = pd.read_csv(genre_history_path) if genre_history_path.is_file() else genres
    canadian_audio = genre_history[genre_history.country_iso3.eq("CAN") & genre_history.format_label.eq("Audiobook")]
    default_genre_year = int(canadian_audio.year.max())
    company_path = project_root / "data/processed/companies.csv"
    company_count = len(pd.read_csv(company_path)) if company_path.exists() else 0
    notebook = nbformat.v4.new_notebook()
    notebook.metadata = {
        "kernelspec": {"display_name": "Global Reading Atlas (.venv)", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": sys.version.split()[0]},
        "title": "Global Reading Atlas | Book and audiobook market research",
        "gra_mode": "public-demand evidence; research prioritisation",
    }
    notebook.cells = [
        md("""
        # Book and audiobook market research
        ### Public audience evidence, industry revenue and company coverage

        A reproducible companion to the Global Reading Atlas dashboard. This notebook uses the **same
        cached observations**, retains editable Python plotting code, and checks its shared tables against
        the dashboard snapshot. It makes no network request and uses no Storytel internal data.

        **Scope:** audiobook listening, paper-book reading, genre preferences, publisher revenue and public
        company information across countries. The company inventory is an initial reviewed set, not a
        complete worldwide census. Revenue and audience participation answer different questions.

        **Case study:** Storytel new-market entry and existing-market growth are separate research tracks.
        Both need commercial evidence beyond public demand surveys.

        **Requested period:** 2022 through the current evidence refresh. Source publication dates and
        observation years remain distinct. The older US phone-survey history is a labelled background check.
        """),
        md(f"""
        ## Evidence at a glance

        - **Industry-wide coverage includes {company_count} reviewed companies and services**, independent US and UK
          publisher revenue, and annual survey waves of daily paper, ebook and audiobook reach in
          Norway and Sweden.
          Company rows include parent/brand overlap and cannot be summed into market share.
        - **{audio.country_iso3.nunique()} countries have audited listening profiles.** Latest reviewed audio waves use different bases:
          Canada and Singapore measure annual listening within reader subsets; the US measures annual
          adult participation; Norway and Sweden measure average-day population reach.
        - **As historical background, US audiobook participation moved from {audio_us.loc[2011, 'participation']:.0f}% in 2011 to
          {audio_us.loc[2021, 'participation']:.0f}% in 2021** during the phone-survey period. The
          **{audio_us.loc[2025, 'participation']:.0f}% result in 2025** uses a different survey mode and stands separately.
        - **Canada supplies format-specific catalogue hypotheses for one explicitly selected survey year.**
          The `GENRE_YEAR` parameter defaults to the latest reviewed wave. The selected-year leaders and
          percentages are calculated below. The audited 2024 baseline remains available; genre years are never pooled.
          Exact genre-subgroup sample sizes are unpublished.
        - **The 2026 Story Report adds a common-question view of genres and listening occasions across
          five existing markets.** These percentages describe listener preferences, not national adoption
          or paid subscription penetration. Only each country's top five responses are published.
        - **These data support research prioritisation for two separate tracks:** new entry and growth in
          existing markets. They cannot identify the best investment country without verified operating
          footprint, language/catalogue rights, addressable paying audience, competition, price,
          acquisition cost and retention evidence.

        Use source-specific profiles and the country evidence table below. Percentages are never converted
        into total listeners or averaged into a country attractiveness score.
        """),
        md("""
        ## Context & Methods

        Audio is the primary metric in this notebook. Eurostat's total book participation includes
        audiobooks, but does not isolate them, so it supplies no audiobook adoption estimate here.

        | Evidence family | What the metric answers | What it cannot answer |
        |:--|:--|:--|
        | US annual adult participation | Share of surveyed adults listening in the prior year | Paid subscription penetration or current revenue |
        | Canada / Singapore annual reader subsets | Listening use within the stated reader base | Share of all residents listening |
        | Norway / Sweden average-day reach | Listening on an average day within each population scope | Annual participation or repeat listening frequency |
        | Canada format-specific genres | Selected genres among the reported within-format reader bases | Catalogue market share or listening hours |

        ### Key Assumptions

        1. Published percentages are stored on a **0–100 scale**. A difference is in percentage points.
        2. Periods, population scopes and denominators remain visible. Equal axis scales help read each
           observation, but do not make the surveys comparable. Annual reader subsets differ from one another.
        3. The US 2011–2021 phone-survey series and 2025 web/phone survey observation stay separate.
           The notebook does not treat the later difference as measured growth across methods.
        4. Format use and genre selections overlap. The Canadian genre questions allow up to three selections;
           missing values remain missing, and percentages need not total 100%.
        5. Singapore's genre question covers mixed reading materials and all reading formats. It does not
           isolate audiobook genres. The notebook keeps it out of the audio catalogue charts.
        6. Aggregate public tables do not provide respondent microdata or survey-design intervals here.
           There are no inferred confidence intervals, causal effects or significance tests.
        7. The candidate-country list below is a user research filter. Storytel-brand presence and
           Storytel-group presence are different questions, so verify both before treating a country as a new-entry candidate.
        8. The Storytel-commissioned April 2026 online-panel study covers adults age 18–79 across five
           countries (5,077 total respondents). Its listener-subgroup eligibility and exact base sizes,
           weighting details and response instructions are unpublished. The overall sample is not the
           denominator for listener preference percentages; unlisted top-five responses remain unreported.

        | Decision track | Demand question | Required business evidence |
        |:--|:--|:--|
        | New entry | Does a defined local audience listen and show willingness to pay? | Verified footprint, local rights, price, competition, acquisition and launch costs |
        | Existing-market growth | Which audience or catalogue opportunity can improve profitable growth? | Local paying penetration, segment conversion, retention, catalogue gaps and marginal contribution |
        """),
        md("""
        ### 1. Set up Python

        In your notebook editor, open this notebook and select the project's `.venv` interpreter. Run all cells in order.
        Inputs are found from any directory inside the project. No user-level kernel registration is required.
        """),
        code(r"""
        from pathlib import Path
        import os
        import json
        import hashlib
        import textwrap
        from importlib.metadata import version

        def find_project_root():
            explicit = os.environ.get("GRA_PROJECT_ROOT")
            candidates = ([Path(explicit)] if explicit else []) + [Path.cwd(), *Path.cwd().parents]
            for candidate in candidates:
                if (candidate / "data/processed/format_profiles.csv").is_file():
                    return candidate.resolve()
            raise FileNotFoundError("Start inside Global Reading Atlas or set GRA_PROJECT_ROOT.")

        ROOT = find_project_root()
        OUTPUT_ROOT = Path(os.environ.get("GRA_NOTEBOOK_OUTPUT_ROOT", ROOT)).resolve()
        FIGURES = OUTPUT_ROOT / "outputs/audiobook_figures"
        FIGURES.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_ROOT / "work/matplotlib"))

        import numpy as np
        import pandas as pd
        import matplotlib
        matplotlib.use("module://matplotlib_inline.backend_inline")
        import matplotlib.pyplot as plt
        from matplotlib.ticker import PercentFormatter
        from IPython.display import display, HTML, Markdown

        plt.rcParams.update({
            "font.family": "DejaVu Sans", "font.size": 11,
            "axes.titlesize": 14, "axes.titleweight": "bold", "axes.labelsize": 11,
            "axes.spines.top": False, "axes.spines.right": False,
            "axes.edgecolor": "#bac6ce", "axes.labelcolor": "#24333c",
            "xtick.color": "#44535d", "ytick.color": "#24333c",
            "figure.facecolor": "white", "axes.facecolor": "white",
            "grid.color": "#e6ebee", "grid.linewidth": 0.8,
            "savefig.facecolor": "white", "savefig.bbox": "tight",
        })
        AUDIO_COLOR = "#296b8c"
        REFERENCE_COLOR = "#a5bac6"
        figure_paths = []

        def show_figure(fig, name):
            path = FIGURES / f"{name}.png"
            fig.savefig(path, dpi=160)
            figure_paths.append(path)
            plt.show()
            plt.close(fig)

        def readable_table(frame, formats=None):
            style = frame.style.hide(axis="index").set_properties(**{
                "text-align": "left", "white-space": "normal", "overflow-wrap": "anywhere",
            })
            if formats:
                style = style.format(formats, na_rep="Not published")
            display(style)
        """),
        md("""
        ### 2. Edit the research filters

        `AUDIO_ONLY=True` keeps the primary table and country figures focused on audio. Set it to `False`
        to inspect overlapping print/ebook formats in the table. Parameters apply to the source inventory,
        country profiles, requested-period history and decision table. US historical and Canadian genre
        reference analyses keep their stated source scopes. `SOURCE_FAMILY` and `PERIOD` match the published values.
        Choose `GENRE_YEAR` explicitly to inspect one Canadian survey wave. Changing it recalculates
        the genre leaders, captions and source locators together; the reader-sample size is not a genre base.
        No filter silently substitutes a total-book measure for missing listening evidence.
        """),
        code(r"""
        CANDIDATE_COUNTRIES = ["CAN", "SGP", "NOR", "SWE", "USA", "FIN", "POL", "BGR"]  # ISO3
        AUDIO_ONLY = True
        START_YEAR = 2022
        END_YEAR = pd.Timestamp.today().year
        PERIOD = "All audited periods"  # "Past 12 months" or "Average day"
        SOURCE_FAMILY = "All audited profiles"
        DECISION_TRACK = "Both"  # "New entry", "Existing-market growth", or "Both"
        SELECTED_2026_GENRE = "Crime/Thriller"  # Original label; only each country's top five are published
        GENRE_YEAR = __DEFAULT_CANADIAN_GENRE_YEAR__  # Latest reviewed Canadian wave; choose 2024 or 2025 explicitly

        """.replace("__DEFAULT_CANADIAN_GENRE_YEAR__", str(default_genre_year))),
        md("""
        ## Data
        ### 3. Load and reconcile the dashboard evidence

        The equality checks compare every shared table cell, including original labels, bases, notes and
        missingness. A changed CSV with a stale dashboard snapshot stops the notebook before analysis.
        The receipt at the end records full SHA-256 hashes of the inputs used.
        """),
        code(r"""
        FILES = {
            "formats": "format_profiles.csv",
            "us": "us_formats.csv",
            "genres": "genre_profiles.csv",
        }
        frames = {name: pd.read_csv(ROOT / "data/processed" / filename) for name, filename in FILES.items()}
        formats, us, genres = frames["formats"], frames["us"], frames["genres"]
        snapshot = json.loads((ROOT / "data/processed/dashboard_snapshot.json").read_text())
        query_names = {"formats": "format_profiles", "us": "us_formats", "genres": "genre_profiles"}
        for name, query in query_names.items():
            dashboard_rows = pd.DataFrame(snapshot["queries"][query]["rows"])
            pd.testing.assert_frame_equal(
                frames[name].reset_index(drop=True), dashboard_rows[frames[name].columns].reset_index(drop=True),
                check_dtype=False, check_like=True,
            )

        OPTIONAL_FILES = {
            "audiobook_history": "audiobook_history.csv",
            "audio_market_evidence": "audio_market_evidence.csv",
            "data_freshness": "data_freshness.csv",
            "format_history": "format_history.csv",
            "genre_history": "genre_history.csv",
            "companies": "companies.csv",
            "industry_metrics": "industry_metrics.csv",
            "storytel_audio_2026": "storytel_audio_2026.csv",
            "audiobook_evidence": "audiobook_evidence.csv",
        }
        optional_frames = {}
        for query, filename in OPTIONAL_FILES.items():
            path = ROOT / "data/processed" / filename
            if path.is_file():
                source_rows = pd.read_csv(path)
                if query not in snapshot["queries"]:
                    raise AssertionError(f"Refresh dashboard snapshot before using {filename}.")
                dashboard_rows = pd.DataFrame(snapshot["queries"][query]["rows"])
                pd.testing.assert_frame_equal(
                    source_rows.fillna("").reset_index(drop=True), dashboard_rows[source_rows.columns].fillna("").reset_index(drop=True),
                    check_dtype=False, check_like=True,
                )
                optional_frames[query] = source_rows

        assert formats.participation.between(0, 100).all(), "Format percentages must use the 0–100 scale."
        assert genres.participation.dropna().between(0, 100).all()
        assert not formats.duplicated(["country_iso3", "year", "format_label"]).any()
        assert not genres.duplicated(["country_iso3", "year", "format_label", "genre_scope", "genre"]).any()
        assert formats[["denominator", "population", "period", "source_url"]].notna().all().all()
        assert set(formats[formats.format_label.eq("Audiobook")].country_iso3) == {"CAN", "SGP", "NOR", "SWE", "USA"}
        assert not genres[genres.country_iso3.eq("SGP")].format_label.eq("Audiobook").any()

        audio_us = us[us.format_label.eq("Audiobook")].sort_values("year").copy()
        method_break = audio_us.method_break.astype(str).str.lower().eq("true")
        us_phone = audio_us[~method_break].copy()
        us_later = audio_us[method_break].copy()
        assert us_phone.year.max() == 2021 and us_later.year.tolist() == [2025]
        assert us_phone.set_index("year").loc[2011, "participation"] == 11
        assert us_phone.set_index("year").loc[2021, "participation"] == 23
        assert us_later.participation.iloc[0] == 26

        assert isinstance(AUDIO_ONLY, bool)
        assert 2022 <= START_YEAR <= END_YEAR
        assert DECISION_TRACK in {"New entry", "Existing-market growth", "Both"}
        assert len(CANDIDATE_COUNTRIES) == len(set(CANDIDATE_COUNTRIES)), "Remove duplicate candidates."
        audio_profiles = optional_frames.get("audiobook_evidence", formats[formats.format_label.eq("Audiobook")]).copy()
        assert audio_profiles.format_label.eq("Audiobook").all()
        assert audio_profiles.participation.dropna().between(0, 100).all()
        format_observations = optional_frames.get("format_history", formats).copy()
        assert format_observations.participation.dropna().between(0, 100).all()
        assert not format_observations.duplicated(["country_iso3", "year", "format_label"]).any()

        latest_formats = (format_observations.sort_values("year")
                          .drop_duplicates(["country_iso3", "format_label", "comparison_group"], keep="last"))
        profile_data = pd.concat([latest_formats[~latest_formats.format_label.eq("Audiobook")], audio_profiles], ignore_index=True)
        assert PERIOD in {"All audited periods", *format_observations.period.unique(), *audio_profiles.period.unique()}
        assert SOURCE_FAMILY in {"All audited profiles", *format_observations.comparison_group.unique(), *audio_profiles.comparison_group.unique()}

        genre_observations = optional_frames.get("genre_history", genres).copy()
        assert genre_observations.participation.dropna().between(0, 100).all()
        assert not genre_observations.duplicated(["country_iso3", "year", "format_label", "genre_scope", "genre"]).any()
        available_genre_years = sorted(genre_observations[genre_observations.country_iso3.eq("CAN") &
                                                       genre_observations.format_label.eq("Audiobook")].year.unique())
        assert GENRE_YEAR in available_genre_years, "Choose a reviewed Canadian genre year."
        assert START_YEAR <= GENRE_YEAR <= END_YEAR, "Keep GENRE_YEAR inside the requested year range."
        canada_audio = genre_observations[genre_observations.country_iso3.eq("CAN") &
                                         genre_observations.format_label.eq("Audiobook") &
                                         genre_observations.year.eq(GENRE_YEAR)].copy()
        assert canada_audio.genre_scope.nunique() == 2
        fiction_leader = (canada_audio[canada_audio.genre_scope.eq("Book fiction genres")]
                          .dropna(subset=["participation"]).sort_values("participation", ascending=False).iloc[0])
        nonfiction_leader = (canada_audio[canada_audio.genre_scope.eq("Book non-fiction genres")]
                             .dropna(subset=["participation"]).sort_values("participation", ascending=False).iloc[0])
        selected = profile_data[profile_data.country_iso3.isin(CANDIDATE_COUNTRIES)].copy()
        selected = selected[selected.year.between(START_YEAR, END_YEAR)]
        if AUDIO_ONLY:
            selected = selected[selected.format_label.eq("Audiobook")]
        if PERIOD != "All audited periods":
            selected = selected[selected.period.eq(PERIOD)]
        if SOURCE_FAMILY != "All audited profiles":
            selected = selected[selected.comparison_group.eq(SOURCE_FAMILY)]
        selected = selected.sort_values(["country", "format_label"])
        selected_audio = selected[selected.format_label.eq("Audiobook")].copy()
        missing_candidates = sorted(set(CANDIDATE_COUNTRIES) - set(selected_audio.country_iso3))
        display(Markdown(f"**Decision track:** {DECISION_TRACK}. **Dashboard tables reconciled.** Snapshot built: `{snapshot['generatedAt']}`. "
                         f"Selected audio profiles: **{len(selected_audio)}**. "
                         f"Candidates with no matching audio adoption/reach observation: **{', '.join(missing_candidates) or 'none'}**."))
        display(Markdown("**Available periods:** " + "; ".join(sorted(set(format_observations.period) | set(audio_profiles.period))) +
                         ". **Source families:** " + "; ".join(sorted(set(format_observations.comparison_group) | set(audio_profiles.comparison_group))) + "."))
        display(Markdown(f"**Canada {GENRE_YEAR} audiobook genres:** {fiction_leader.genre} leads the selected fiction list "
                         f"at **{fiction_leader.participation:.0f}%**; {nonfiction_leader.genre} leads the separate nonfiction list "
                         f"at **{nonfiction_leader.participation:.0f}%**. Exact genre-subgroup n is unpublished. "
                         f"Available Canadian genre waves: **{', '.join(str(int(year)) for year in available_genre_years)}**."))
        """),
        md("""
        ### 4. Inspect selected listening observations

        This is an alphabetical source inventory, not an adoption leaderboard. Canada and Singapore
        have different reader bases. Sweden and Norway report daily reach with different age scopes.
        The US measures annual participation among surveyed adults. Every row needs its base.
        Each format uses its latest reviewed wave within a source family, with its own published year and denominator.
        """),
        code(r"""
        observation_table = selected[["country", "year", "format_label", "participation", "period", "denominator"]].rename(columns={
            "country": "Country", "year": "Year", "format_label": "Format", "participation": "Reported (%)",
            "period": "Recall period", "denominator": "Base",
        })
        readable_table(observation_table, {"Year": "{:.0f}", "Reported (%)": "{:.0f}"})
        base_table = selected_audio[["country", "population", "notes", "source_id"]].rename(columns={
            "country": "Country", "population": "Population", "notes": "Interpretation", "source_id": "Source ID",
        })
        readable_table(base_table)
        """),
        md("""
        ## Results
        ### 5. Read each country's audio metric on its own base

        Separate panels preserve the different questions. The common 0–100 scale shows the published
        percentage within each base; it does not establish cross-country comparability.
        """),
        code(r"""
        if selected_audio.empty:
            display(Markdown("No selected country has matching audio evidence. Adjust the filters or add a reviewed source."))
        else:
            panel_count = len(selected_audio)
            fig, axes = plt.subplots(panel_count, 1, figsize=(10.5, 2.0 * panel_count + 1.0), squeeze=False)
            for ax, row in zip(axes.ravel(), selected_audio.itertuples()):
                ax.barh([0], [row.participation], height=0.34, color=AUDIO_COLOR)
                ax.set_xlim(0, 100)
                ax.set_ylim(-0.5, 0.55)
                ax.set_yticks([])
                ax.set_xticks([0, 25, 50, 75, 100])
                ax.xaxis.set_major_formatter(PercentFormatter(100, decimals=0))
                ax.grid(axis="x", zorder=0)
                ax.set_axisbelow(True)
                ax.set_title(f"{row.country} · {row.year} · {row.period}", loc="left", pad=26)
                ax.text(0, 1.07, textwrap.fill(f"Base: {row.denominator}; {row.population}", 110),
                        transform=ax.transAxes, fontsize=9.5, color="#526571", va="bottom")
                ax.text(row.participation + 1.4, 0, f"{row.participation:.0f}%", va="center", fontweight="bold")
                ax.spines["left"].set_visible(False)
            fig.suptitle("Audiobook use: source-specific country profiles", x=0.05, ha="left", fontsize=18, fontweight="bold")
            fig.supxlabel("Published percentage within each stated base", fontsize=11, y=0.025)
            fig.text(0.05, 0.005, "Sources: BookNet Canada; NLB Singapore; SSB; Nordicom; Pew. See exact links below.",
                     fontsize=9, color="#526571")
            fig.subplots_adjust(top=0.90, bottom=0.10, left=0.06, right=0.94, hspace=0.90)
            show_figure(fig, "01_audio_country_profiles")
        """),
        md("""
        ### 6. Track observed waves from 2022 through the current year

        Each panel uses one country, source family, period and population/base definition. Bars show
        published observations only. Blank years are missing waves, never zero or an interpolated estimate.
        Publication and checking dates belong in the freshness table rather than the observation-year axis.
        """),
        code(r"""
        history = optional_frames.get("audiobook_history")
        observed_history = pd.DataFrame()
        history_figure_created = False
        if history is None:
            display(Markdown("The requested-period listening history file is not present in this snapshot."))
        else:
            assert history.participation.dropna().between(0, 100).all()
            history_scope = history[history.country_iso3.isin(CANDIDATE_COUNTRIES) & history.year.between(START_YEAR, END_YEAR)].copy()
            if PERIOD != "All audited periods":
                history_scope = history_scope[history_scope.period.eq(PERIOD)]
            if SOURCE_FAMILY != "All audited profiles":
                history_scope = history_scope[history_scope.comparison_group.eq(SOURCE_FAMILY)]
            signature = ["country", "comparison_group", "period", "population", "denominator", "source_id"]
            assert not history_scope.duplicated(signature + ["year"]).any()
            observed_history = history_scope.dropna(subset=["participation"]).copy()
            groups = list(history_scope.groupby(signature, sort=True, dropna=False))
            visible_groups = groups[:8]
            if not visible_groups or observed_history.empty:
                display(Markdown("No published listening wave matches these country, year and source filters."))
            else:
                columns = 2 if len(visible_groups) > 1 else 1
                rows = int(np.ceil(len(visible_groups) / columns))
                fig, axes = plt.subplots(rows, columns, figsize=(11.6, rows * 3.8 + 0.8), squeeze=False)
                for ax, (scope_key, group) in zip(axes.ravel(), visible_groups):
                    country, family, period, population, denominator, source_id = scope_key
                    wave = group.dropna(subset=["participation"]).sort_values("year")
                    ax.bar(wave.year, wave.participation, width=0.5, color=AUDIO_COLOR)
                    for value in wave.itertuples():
                        ax.text(value.year, value.participation + 2, f"{value.participation:.0f}%", ha="center", fontsize=10)
                    ax.set_xlim(START_YEAR - 0.6, END_YEAR + 0.6)
                    ax.set_xticks(range(START_YEAR, END_YEAR + 1))
                    ax.set_ylim(0, 100)
                    ax.set_yticks([0, 25, 50, 75, 100])
                    ax.yaxis.set_major_formatter(PercentFormatter(100, decimals=0))
                    ax.grid(axis="y")
                    ax.set_axisbelow(True)
                    ax.set_title(f"{country} · {period}", loc="left", pad=35)
                    ax.text(0, 1.06, textwrap.fill(str(denominator), 55), transform=ax.transAxes,
                            fontsize=9, color="#526571", va="bottom")
                    ax.set_xlabel("Observed survey year; blank years = no reviewed wave")
                for unused_ax in axes.ravel()[len(visible_groups):]:
                    unused_ax.set_visible(False)
                fig.suptitle(f"Audiobook observations · {START_YEAR}–{END_YEAR}", x=0.065, ha="left", fontsize=18, fontweight="bold")
                fig.text(0.065, 0.018, "Source-specific panels; no country ranking or gap filling. Exact populations and source locators are in the table below.",
                         fontsize=9, color="#526571")
                fig.subplots_adjust(left=0.08, right=0.97, top=0.86, bottom=0.12, hspace=0.85, wspace=0.30)
                show_figure(fig, "02_audio_observed_history")
                history_figure_created = True
                if len(groups) > 8:
                    display(Markdown(f"Showing eight of {len(groups)} source-scope panels, in alphabetical order. Narrow the candidate list for the remaining panels."))
            history_table = history_scope[["country", "year", "participation", "period", "denominator", "evidence_locator"]].sort_values(["country", "year"]).rename(columns={
                "country": "Country", "year": "Year", "participation": "Audio (%)", "period": "Recall period",
                "denominator": "Published base", "evidence_locator": "Evidence locator",
            })
            readable_table(history_table.head(25), {"Year": "{:.0f}", "Audio (%)": "{:.0f}"})
            if len(history_table) > 25:
                display(Markdown(f"Showing 25 of {len(history_table)} selected waves. Full records remain in `data/processed/audiobook_history.csv`."))
        """),
        md("""
        ### 7. Check historical US adoption as background

        Pew's phone-survey observations provide a consistent US history through 2021. Calendar-spaced
        points retain the irregular survey years. **2011–2021 lies outside the requested current-period
        analysis.** A separate panel shows the 2025 method period; the notebook makes no growth inference across modes.
        """),
        code(r"""
        phone_start = us_phone.iloc[0]
        phone_end = us_phone.iloc[-1]
        phone_change = phone_end.participation - phone_start.participation
        fig, (ax_history, ax_later) = plt.subplots(1, 2, figsize=(11.5, 4.8), gridspec_kw={"width_ratios": [3.8, 1.2]})
        ax_history.plot(us_phone.year, us_phone.participation, color=AUDIO_COLOR, marker="o", linewidth=2.2)
        for row in us_phone.itertuples():
            ax_history.annotate(f"{row.participation:.0f}%", (row.year, row.participation), xytext=(0, 8),
                                textcoords="offset points", ha="center", fontsize=10)
        ax_history.set_xticks(us_phone.year)
        ax_history.set_xlim(2010.5, 2021.5)
        ax_history.set_title("2011–2021 · phone surveys", loc="left")
        ax_history.set_ylabel("US adults listening in prior 12 months (%)")
        ax_history.text(0.02, 0.89, f"Observed change: +{phone_change:.0f} percentage points", transform=ax_history.transAxes,
                        fontsize=11, color=AUDIO_COLOR, fontweight="bold")
        later_value = us_later.participation.iloc[0]
        ax_later.bar([2025], [later_value], width=0.5, color=REFERENCE_COLOR, edgecolor=AUDIO_COLOR, linewidth=1.3)
        ax_later.text(2025, later_value + 1, f"{later_value:.0f}%", ha="center", fontweight="bold")
        ax_later.set_title("2025 · changed mode", loc="left")
        ax_later.set_xticks([2025])
        ax_later.set_xlim(2024.4, 2025.6)
        for ax in (ax_history, ax_later):
            ax.set_ylim(0, 35)
            ax.set_yticks([0, 10, 20, 30])
            ax.yaxis.set_major_formatter(PercentFormatter(100, decimals=0))
            ax.grid(axis="y")
            ax.set_axisbelow(True)
        fig.suptitle("US audiobook participation across survey periods", x=0.07, ha="left", fontsize=18, fontweight="bold")
        fig.text(0.07, 0.025, "Source: Pew published data table. All US adults age 18+; previous 12 months. No line crosses the method break.",
                 fontsize=9, color="#526571")
        fig.subplots_adjust(left=0.08, right=0.97, top=0.82, bottom=0.16, wspace=0.34)
        show_figure(fig, "02_us_audio_history")
        display(Markdown(f"During the phone-survey period, reported participation rose **{phone_change:.0f} percentage points** "
                         f"from **{phone_start.participation:.0f}%** to **{phone_end.participation:.0f}%**. "
                         "This is descriptive adoption evidence; the tables do not identify paid listening, Storytel demand, or causal drivers."))
        """),
        md("""
        ### 8. Develop Canadian audiobook fiction hypotheses

        The genre charts use the explicitly selected `GENRE_YEAR`, with separate fiction and nonfiction
        audiobook reader bases. Bars show that wave's published selections. Source dashes remain
        **not published**, rather than zero. Exact within-format genre base sizes and uncertainty are
        unavailable; the overall reader sample is not a genre-subgroup denominator.
        """),
        code(r"""
        assert canada_audio.year.eq(GENRE_YEAR).all(), "Do not pool Canadian genre years."
        if GENRE_YEAR == 2024:
            assert canada_audio[(canada_audio.genre_scope.eq("Book fiction genres")) &
                                (canada_audio.genre.eq("Mysteries or Thrillers"))].participation.iloc[0] == 46
            assert canada_audio[(canada_audio.genre_scope.eq("Book non-fiction genres")) &
                                (canada_audio.genre.eq("History"))].participation.iloc[0] == 34
            assert canada_audio[canada_audio.genre.eq("Comics or Graphic Novels")].participation.isna().all()
        genre_pages = {2024: {"Book fiction genres": 32, "Book non-fiction genres": 33},
                       2025: {"Book fiction genres": 35, "Book non-fiction genres": 37}}
        assert GENRE_YEAR in genre_pages, "Review and register PDF genre page locators for this wave."

        def audio_genre_chart(scope, title, name):
            table = canada_audio[canada_audio.genre_scope.eq(scope)].copy()
            table = table.sort_values("participation", ascending=False, na_position="last")
            assert table.source_url.nunique() == 1 and table.population.nunique() == 1
            page = genre_pages[GENRE_YEAR][scope]
            observed = table.participation.notna()
            y = np.arange(len(table))
            fig, ax = plt.subplots(figsize=(11, 6.8))
            ax.barh(y[observed], table.loc[observed, "participation"], color=AUDIO_COLOR, height=0.58)
            ax.set_yticks(y, table.genre)
            ax.invert_yaxis()
            ax.set_ylim(len(table) - 0.35, -0.65)
            ax.set_xlim(0, 60)
            ax.set_xticks([0, 10, 20, 30, 40, 50, 60])
            ax.xaxis.set_major_formatter(PercentFormatter(100, decimals=0))
            ax.set_xlabel("Selecting genre within the published audiobook reader base (%)")
            ax.grid(axis="x")
            ax.set_axisbelow(True)
            for position, value in zip(y, table.participation):
                if pd.isna(value):
                    ax.text(1, position, "Not published", va="center", color="#687781", fontstyle="italic")
                else:
                    ax.text(value + 0.8, position, f"{value:.0f}%", va="center", fontsize=11)
            ax.set_title(title, loc="left", pad=27)
            ax.text(0, 1.025, textwrap.fill(f"Canada · {GENRE_YEAR} · {table.population.iloc[0]}", 100),
                    transform=ax.transAxes, fontsize=9.5, color="#526571")
            fig.text(0.02, 0.025,
                     f"Source: BookNet Canada {GENRE_YEAR}, printed p.{page}. Up to three choices; categories overlap. Exact subgroup n unpublished.",
                     fontsize=9, color="#526571")
            fig.subplots_adjust(left=0.31, right=0.96, top=0.84, bottom=0.15)
            show_figure(fig, name)
            display(Markdown(f"**Canada {GENRE_YEAR} source:** [BookNet Canada, printed p.{page}]({table.source_url.iloc[0]}). "
                             f"**Reported genre base:** {table.denominator.iloc[0]}."))
            return table

        fiction_audio = audio_genre_chart("Book fiction genres", "Audiobook fiction: published genre selections",
                                         "03_canada_audio_fiction")
        top_fiction = fiction_audio.dropna(subset=["participation"]).iloc[0]
        display(Markdown(f"**Canada {GENRE_YEAR} — {top_fiction.genre}: {top_fiction.participation:.0f}%** is the leading reported fiction selection. "
                         "Use it as an English-language catalogue hypothesis to validate against listening, conversion and retention."))
        """),
        md("""
        ### 9. Develop Canadian nonfiction hypotheses

        This is a separate reader base from the fiction chart. A fiction/nonfiction percentage ratio would
        not measure their relative market sizes or catalogue value.
        """),
        code(r"""
        nonfiction_audio = audio_genre_chart("Book non-fiction genres", "Audiobook nonfiction: published subject selections",
                                            "04_canada_audio_nonfiction")
        top_nonfiction = nonfiction_audio.dropna(subset=["participation"]).iloc[0]
        display(Markdown(f"**Canada {GENRE_YEAR} — {top_nonfiction.genre}: {top_nonfiction.participation:.0f}%** leads the reported nonfiction choices. "
                         "Use the selected-wave categories as catalogue hypotheses, subject to local rights and commercial validation."))
        """),
        md("""
        ### 10. Compare the same 2026 audiobook genre question

        The Storytel-commissioned report asks the same genre question across Sweden, Norway, Finland,
        Poland and Bulgaria. The selected category is an exact original label. Each percentage describes
        the published listener base, not all adults or Storytel customers. Top-five publication means an
        absent category is **unreported**, even if it appears in another country.

        These two 2026 reference figures use the candidate-country list and requested-year range.
        Adoption/reach period and source-family filters above do not change their listener-preference definition.
        """),
        code(r"""
        storytel = optional_frames.get("storytel_audio_2026")
        storytel_genre_figure_created = False
        storytel_moment_figure_created = False
        storytel_scope = pd.DataFrame()
        research_metadata_path = ROOT / "data/curated/storytel_research_metadata.json"
        research_metadata = None
        if storytel is None:
            display(Markdown("The validated 2026 common-question source is absent from this snapshot."))
        else:
            assert storytel.participation.between(0, 100).all()
            assert set(storytel.record_type) == {"genre", "moment"}
            assert storytel.format_label.eq("Audiobook").all()
            assert not storytel.duplicated(["country_iso3", "year", "record_type", "item"]).any()
            assert storytel.groupby(["country_iso3", "record_type"]).size().eq(5).all()
            assert storytel.sample_size.isna().all(), "Listener-subgroup n is unpublished."
            if research_metadata_path.is_file():
                research_metadata = json.loads(research_metadata_path.read_text())
                assert research_metadata["source_url"] in set(storytel.source_url)
                assert len(research_metadata["sha256"]) == 64
                display(Markdown(
                    f"**Fieldwork:** {research_metadata['fieldwork']}. **Published:** {research_metadata['publication_date']}. "
                    f"**Overall sample:** {research_metadata['total_sample']:,}; this is not the listener denominator. "
                    f"**Question:** {research_metadata['genre_question']}"
                ))
            genre_labels = sorted(storytel[storytel.record_type.eq("genre")].item.unique())
            assert SELECTED_2026_GENRE in genre_labels, "Use an original published genre label."
            display(Markdown("**Available original genre labels:** " + "; ".join(genre_labels) + "."))
            storytel_scope = storytel[storytel.country_iso3.isin(CANDIDATE_COUNTRIES) & storytel.year.between(START_YEAR, END_YEAR)].copy()
            comparison_countries = sorted(storytel_scope.country.unique())
            if not comparison_countries:
                display(Markdown("No candidate country has a 2026 listener-preference record in the selected year range."))
            else:
                selected_genre_rows = storytel_scope[storytel_scope.record_type.eq("genre") & storytel_scope.item.eq(SELECTED_2026_GENRE)]
                genre_values = selected_genre_rows.set_index("country").participation.reindex(comparison_countries)
                y = np.arange(len(genre_values))
                published = genre_values.notna().to_numpy()
                fig, ax = plt.subplots(figsize=(10.8, 5.5))
                ax.barh(y[published], genre_values.to_numpy()[published], color=AUDIO_COLOR, height=0.5)
                ax.set_yticks(y, comparison_countries)
                ax.set_ylim(len(genre_values) - 0.35, -0.65)
                ax.set_xlim(0, 100)
                ax.set_xticks([0, 25, 50, 75, 100])
                ax.xaxis.set_major_formatter(PercentFormatter(100, decimals=0))
                ax.grid(axis="x")
                ax.set_axisbelow(True)
                for position, value in zip(y, genre_values):
                    if pd.isna(value):
                        ax.text(1, position, "Unreported in top five", va="center", color="#687781", fontstyle="italic")
                    else:
                        ax.text(value + 1.2, position, f"{value:.0f}%", va="center", fontweight="bold")
                ax.set_title(f"2026 audiobook listeners · {SELECTED_2026_GENRE}", loc="left", pad=30)
                ax.text(0, 1.035, "Common question across five online panels; age 18–79; exact listener subgroup n unpublished",
                        transform=ax.transAxes, fontsize=9.5, color="#526571")
                ax.set_xlabel("Published listener responses (%)")
                fig.text(0.02, 0.022,
                         "Source: The 2026 Story Report, p.14. April 2026 fieldwork; Storytel / Trackit Insight. Top-five selections only.",
                         fontsize=9, color="#526571")
                fig.subplots_adjust(left=0.15, right=0.95, top=0.80, bottom=0.17)
                show_figure(fig, "05_storytel_2026_selected_genre")
                storytel_genre_figure_created = True
                genre_comparison_table = genre_values.rename("Selected genre (%)").reset_index().rename(columns={"country": "Country"})
                readable_table(genre_comparison_table, {"Selected genre (%)": "{:.0f}"})
                display(Markdown("This is a common-question preference comparison. It does not establish listener-market size, "
                                 "statistical significance, country investment priority or catalogue ROI."))
        """),
        md("""
        ### 11. Explore listening moments for existing-market growth

        The heatmap retains the union of published listening occasions. **Unreported** cells indicate a
        category outside that country's published top five. They cannot be interpreted as zero usage.
        Occasions overlap, and no percentages are added together.
        """),
        code(r"""
        if not storytel_scope.empty:
            moments = storytel_scope[storytel_scope.record_type.eq("moment")]
            moment_matrix = moments.pivot(index="item", columns="country", values="participation")
            moment_matrix = moment_matrix.reindex(index=sorted(moment_matrix.index), columns=sorted(moment_matrix.columns))
            matrix = moment_matrix.to_numpy(dtype=float)
            cmap = matplotlib.colors.LinearSegmentedColormap.from_list("audio_moments", ["#f0f5f8", AUDIO_COLOR])
            cmap.set_bad("#f2f3f4")
            fig, ax = plt.subplots(figsize=(11.6, 6.8))
            image = ax.imshow(np.ma.masked_invalid(matrix), cmap=cmap, vmin=0, vmax=60, aspect="auto")
            ax.set_xticks(np.arange(len(moment_matrix.columns)), moment_matrix.columns)
            ax.set_yticks(np.arange(len(moment_matrix.index)), [textwrap.fill(label, 26) for label in moment_matrix.index])
            ax.tick_params(axis="both", length=0, pad=9)
            for row in range(matrix.shape[0]):
                for column in range(matrix.shape[1]):
                    value = matrix[row, column]
                    if np.isnan(value):
                        ax.text(column, row, "Unreported", ha="center", va="center", fontsize=9, color="#687781")
                    else:
                        rgb = np.array(cmap(image.norm(value))[:3])
                        linear_rgb = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
                        luminance = float(linear_rgb @ np.array([0.2126, 0.7152, 0.0722]))
                        text_color = "white" if 1.05 / (luminance + 0.05) >= (luminance + 0.05) / 0.05 else "black"
                        ax.text(column, row, f"{value:.0f}%", ha="center", va="center", fontsize=12,
                                color=text_color)
            ax.set_title("2026 audiobook listeners · published listening occasions", loc="left", pad=42)
            ax.text(0, 1.045, "Online panels; age 18–79; only each country's top five occasions are published",
                    transform=ax.transAxes, fontsize=10, color="#526571")
            colorbar = fig.colorbar(image, ax=ax, fraction=0.035, pad=0.04)
            colorbar.set_label("Published listener responses (%)", labelpad=10)
            colorbar.set_ticks([0, 20, 40, 60], labels=["0%", "20%", "40%", "60%"])
            fig.text(0.025, 0.02,
                     "Source: The 2026 Story Report, p.13. April 2026; Storytel / Trackit Insight. Exact subgroup n and response instructions unpublished.",
                     fontsize=9, color="#526571")
            fig.subplots_adjust(left=0.27, right=0.91, top=0.81, bottom=0.13)
            show_figure(fig, "06_storytel_2026_listening_moments")
            storytel_moment_figure_created = True
            display(Markdown("Use observed occasions to develop audience and messaging hypotheses in existing markets. "
                             "Validate them with local conversion, listening and retention evidence before allocating incremental spend."))
        else:
            display(Markdown("No selected 2026 listening-occasion observations are available."))
        """),
        md("""
        ### 12. Keep the country decision auditable

        The source inventory marks the evidence available here. **Available** describes a cached survey
        observation; it does not rate commercial attractiveness. Missing annual adoption, genre evidence,
        or current Storytel status remains a research task.

        If the project's market-evidence CSV is present, the next cell displays its candidate-country
        records as a bounded research table. It does not combine fields into a score.
        """),
        code(r"""
        countries = format_observations[["country_iso3", "country"]].drop_duplicates().sort_values("country")
        if storytel is not None:
            countries = pd.concat([countries, storytel[["country_iso3", "country"]]], ignore_index=True).drop_duplicates().sort_values("country")
        evidence_rows = []
        for row in countries.itertuples():
            profiles = audio_profiles[audio_profiles.country_iso3.eq(row.country_iso3)].sort_values("year", ascending=False)
            profile = profiles.iloc[0] if not profiles.empty else None
            selected_genres = genre_observations[genre_observations.country_iso3.eq(row.country_iso3) &
                                                genre_observations.format_label.eq("Audiobook") &
                                                genre_observations.year.eq(GENRE_YEAR)]
            audio_genre_count = selected_genres.participation.notna().sum()
            common_genre_count = 0 if storytel is None else len(storytel[storytel.country_iso3.eq(row.country_iso3) & storytel.record_type.eq("genre")])
            genre_coverage = f"{audio_genre_count} published {GENRE_YEAR} selections" if audio_genre_count else "Unavailable here"
            if common_genre_count:
                genre_coverage = f"{common_genre_count} published 2026 selections"
            evidence_rows.append({
                "Country": row.country,
                "Audio observation": f"{profile.participation:.0f}% · {profile.period} · {profile.year}" if profile is not None else "Adoption/reach unavailable here",
                "Published base": profile.denominator if profile is not None else "2026 listener-preference base only",
                "Audio genres": genre_coverage,
                "Consistent audio history": ("2011–2021 phone surveys" if row.country_iso3 == "USA" else
                                             "See 2022+ source-scope panels" if history is not None and row.country_iso3 in set(history.country_iso3) else "Unavailable here"),
            })
        evidence_table = pd.DataFrame(evidence_rows)
        readable_table(evidence_table)

        market_path = ROOT / "data/processed/audio_market_evidence.csv"
        market_evidence = None
        if market_path.is_file():
            market_evidence = optional_frames["audio_market_evidence"].copy()
            iso_column = next((column for column in ["country_iso3", "iso3"] if column in market_evidence.columns), None)
            if iso_column:
                market_evidence = market_evidence[market_evidence[iso_column].isin(CANDIDATE_COUNTRIES)]
            if DECISION_TRACK != "Both" and "decision_route" in market_evidence.columns:
                route_keyword = "entry" if DECISION_TRACK == "New entry" else "growth"
                market_evidence = market_evidence[market_evidence.decision_route.str.contains(route_keyword, case=False, na=False)]

            identity = [column for column in [iso_column, "country"] if column and column in market_evidence.columns]
            columns = [column for column in market_evidence.columns if column not in identity]
            display(Markdown("**Project market-evidence table** — source-specific research records; no composite score."))
            for start in range(0, len(columns), 4):
                readable_table(market_evidence[identity + columns[start:start + 4]].head(20))
            if len(market_evidence) > 20:
                display(Markdown(f"Showing the first 20 of {len(market_evidence)} selected evidence records in each column group."))
        else:
            display(Markdown("The optional market-evidence file is absent. The audited listening inventory above remains available."))
        """),
        md("""
        ### 13. Check refresh status and evidence age

        Observation year, publication date, source-check date and last successful data refresh answer
        different questions. An automated check can succeed without a new survey wave. A failed retrieval
        does not erase the last validated cached observation or make it current.
        """),
        code(r"""
        freshness = optional_frames.get("data_freshness")
        if freshness is None:
            display(Markdown("No structured refresh-status file is present. Review the snapshot build timestamp and source receipt above."))
        else:

            identity_columns = [column for column in ["source_id", "country", "source"] if column in freshness.columns]
            other_columns = [column for column in freshness.columns if column not in identity_columns]
            for start in range(0, len(other_columns), 4):
                readable_table(freshness[identity_columns + other_columns[start:start + 4]].head(20))
            if len(freshness) > 20:
                display(Markdown(f"Showing 20 of {len(freshness)} source-status rows. Full records remain in `data/processed/data_freshness.csv`."))
        """),
        md("""
        ## Paper books, audiobooks and the wider industry

        Public evidence covers national surveys, independent trade associations, company reporting and
        library platforms. Storytel's commissioned survey is one source in this wider inventory. The company
        register is an initial reviewed list, not an exhaustive census of every publisher and service.
        """),
        code(r"""
        national_formats = optional_frames.get("format_history")
        extra_industry_figures = 0
        if national_formats is not None:
            assert not national_formats.duplicated(["country_iso3", "year", "format_label"]).any()
            assert national_formats.participation.dropna().between(0, 100).all()
            FORMAT_HISTORY_COUNTRY = "Sweden"  # Change to "Norway"; preserve each survey's age scope
            national_scope = national_formats[national_formats.country.eq(FORMAT_HISTORY_COUNTRY) & national_formats.year.between(START_YEAR, END_YEAR)].copy()
            assert national_scope.period.nunique() == 1 and national_scope.denominator.nunique() == 1
            fig, ax = plt.subplots(figsize=(11.6, 5.4))
            palette = {"Print": "#91a1ab", "Ebook": "#c6d2d9", "Audiobook": AUDIO_COLOR}
            offsets = {"Print": -0.24, "Ebook": 0.0, "Audiobook": 0.24}
            for label in ["Print", "Ebook", "Audiobook"]:
                series = national_scope[national_scope.format_label.eq(label)].dropna(subset=["participation"])
                ax.bar(series.year + offsets[label], series.participation, width=0.22, color=palette[label], label=label)
                for row in series.itertuples():
                    ax.text(row.year + offsets[label], row.participation + 1.5, f"{row.participation:.0f}%", ha="center", fontsize=9)
            ax.set_xticks(range(START_YEAR, END_YEAR + 1))
            ax.set_xlim(START_YEAR - 0.6, END_YEAR + 0.6)
            ax.set_ylim(0, 100)
            ax.yaxis.set_major_formatter(PercentFormatter(100, decimals=0))
            ax.grid(axis="y"); ax.set_axisbelow(True)
            ax.legend(frameon=False, ncol=3, loc="upper right")
            ax.set_title(f"{FORMAT_HISTORY_COUNTRY}: daily reach by book format", loc="left", pad=30)
            ax.text(0, 1.035, f"Base: {national_scope.denominator.iloc[0]}; formats overlap", transform=ax.transAxes, fontsize=10, color="#526571")
            ax.set_xlabel("Survey year; absent bars are unpublished waves, not zero")
            fig.text(0.02, 0.015, "Sources: Nordicom annual results or SSB report and table 11556. Exact source URLs and definitions remain in format_history.csv.", fontsize=9, color="#526571")
            fig.subplots_adjust(left=0.08, right=0.97, top=0.81, bottom=0.17)
            show_figure(fig, "07_paper_ebook_audio_history")
            extra_industry_figures += 1
            readable_table(national_scope[["country", "year", "format_label", "participation", "denominator", "source_url"]], {"year": "{:.0f}", "participation": "{:.0f}"})
        """),
        md("""
        ### Independent market revenue evidence

        Revenue describes sales value, not the number of readers, listeners or paying subscribers.
        Choose one series with its published geography, unit and scope. Do not calculate an audiobook
        share by dividing estimates from different associations or incompatible reporting populations.
        Amounts come from original releases; later reports revise earlier estimates. Differences between
        bars do not establish annual growth or decline. The publication dates and notes remain part of the evidence.
        """),
        code(r"""
        industry = optional_frames.get("industry_metrics")
        if industry is not None and not industry.empty:
            assert industry.value.dropna().ge(0).all()
            assert not industry.duplicated(["series_id", "year"]).any()
            INDUSTRY_SERIES = sorted(industry.series_id.unique())[0]  # Edit using the inventory below
            display(Markdown("**Available market series:** " + "; ".join(sorted(industry.series_id.unique()))))
            market_series = industry[industry.series_id.eq(INDUSTRY_SERIES) & industry.year.between(START_YEAR, END_YEAR)].sort_values("year")
            assert market_series.unit.nunique() == 1 and market_series.scope.nunique() == 1
            definition = market_series.iloc[0]
            fig, ax = plt.subplots(figsize=(11.6, 5.4))
            ax.bar(market_series.year, market_series.value, width=0.5, color=AUDIO_COLOR)
            for row in market_series.itertuples():
                ax.annotate(f"{row.value:,.0f}", (row.year, row.value), xytext=(0, 6), textcoords="offset points", ha="center", fontsize=10)
            ax.set_xticks(range(START_YEAR, END_YEAR + 1))
            ax.set_xlim(START_YEAR - 0.6, END_YEAR + 0.6)
            ax.set_ylim(0, float(market_series.value.max()) * 1.18)
            ax.set_ylabel(definition.unit)
            ax.set_title(f"{definition.country}: {definition.metric} (as published)", loc="left", pad=45)
            ax.text(0, 1.04, textwrap.fill(str(definition.scope), 100), transform=ax.transAxes, fontsize=9, color="#526571")
            ax.grid(axis="y"); ax.set_axisbelow(True)
            ax.set_xlabel("Observation year; absent years are unavailable")
            fig.text(0.02, 0.015, "Published annual observations; different report vintages. No continuous growth, cross-source market-share or audience calculation.", fontsize=9, color="#526571")
            fig.subplots_adjust(left=0.11, right=0.97, top=0.77, bottom=0.17)
            show_figure(fig, "08_industry_market_revenue")
            extra_industry_figures += 1
            readable_table(market_series[["country", "year", "value", "unit", "publication_date", "notes"]], {"year": "{:.0f}", "value": "{:,.1f}"})
        """),
        md("""
        ### Company and platform coverage

        The reviewed register includes audiobook services, print publishers, retailers and library
        platforms. Brand, parent, availability and reporting scope have separate meanings. A service's
        availability does not establish its national subscriber count. Blank or unextracted metrics remain
        missing. Company reporting can cover several formats or business divisions.
        """),
        code(r"""
        companies = optional_frames.get("companies")
        if companies is not None:
            assert companies.company_id.is_unique
            assert companies.source_url.str.startswith("https://").all()
            display(Markdown(f"**{len(companies)} reviewed company/platform records.** This initial inventory is not an exhaustive company census."))
            readable_table(companies[["company", "parent_company", "formats", "business_model", "public_data_status"]])
            readable_table(companies[["company", "geographic_scope", "source_url", "reviewed_on", "notes"]])
        """),
        md("""
        ## Takeaways

        1. **Start with the right audio question.** For addressable demand, obtain annual audiobook
           participation among a defined adult population. Daily reach and reader-subset listening are
           useful profiles, but cannot replace that denominator.
        2. **Keep new entry and existing-market growth separate.** Canada has format-specific
           audio genres; the US has consistent historical adoption evidence; Singapore has an annual
           e-audiobook observation within a reader subset. These strengths inform what can be studied next.
           Verify brand and group presence before assigning an entry track. Use local acquisition,
           retention and catalogue evidence for existing-market growth. The notebook cannot establish an investment winner.
        3. **Use Nordic daily reach as an operating benchmark.** Sweden and Norway demonstrate measured
           daily listening within their stated age populations. Compare future extracts within a matched
           scope before making a ranking.
        4. **Turn selected-year Canadian genres into testable catalogue questions.** Keep `GENRE_YEAR`
           and the calculated fiction/nonfiction leaders visible. Check local rights, language fit, title breadth, listening
           hours, completion, acquisition and retention before treating those selections as catalogue ROI.
           The 2026 common-question listener data supplies further genre and occasion hypotheses across
           five existing markets. Its unreported top-five categories remain unknown.
        5. **Close the decision gaps before investment.** Verify Storytel's current presence and entry
           constraints. Add local audiobook paid penetration, price willingness, competitor share,
           acquisition cost, retention and contribution margin from governed sources or direct research.

        **Next useful analysis:** a source-matched candidate-country demand study plus a unit-economics
        scenario using verified business inputs. Keep assumptions, denominators and sensitivity ranges visible.
        """),
        md("""
        ### Sources and reproducibility receipt

        Source links point to the original publisher documents used in the cached evidence. Full input
        hashes identify this notebook run. They detect file changes, rather than certifying survey quality.
        Shared row equality above ensures this notebook and the current dashboard describe the same data.
        """),
        code(r"""
        source_table = pd.concat([formats, profile_data, audio_profiles, canada_audio], ignore_index=True)[["country", "year", "source_id", "source_url", "evidence_locator"]].drop_duplicates().sort_values(["country", "year"])
        if storytel is not None:
            source_table = pd.concat([source_table, pd.DataFrame([{
                "country": "Five common-question markets", "year": 2026, "source_id": "storytel_story_report_2026",
                "source_url": storytel.source_url.iloc[0], "evidence_locator": "2026 report pp.13–14; listener occasions and genres",
            }])], ignore_index=True)
        source_table["Original source"] = source_table.source_url.map(lambda url: f'<a href="{url}" target="_blank">Publisher document</a>')
        source_html = source_table[["country", "year", "source_id", "Original source", "evidence_locator"]].rename(columns={
            "country": "Country", "year": "Survey year", "source_id": "Source ID", "evidence_locator": "Evidence locator",
        }).to_html(index=False, escape=False)
        display(HTML(source_html))
        input_paths = [ROOT / "data/processed" / filename for filename in FILES.values()]
        input_paths += [ROOT / "data/processed/dashboard_snapshot.json", ROOT / "data/curated/source_checks.json"]
        input_paths += [ROOT / "data/processed" / OPTIONAL_FILES[query] for query in optional_frames]
        if research_metadata_path.is_file():
            input_paths.append(research_metadata_path)
        receipt = pd.DataFrame([{
            "Input": path.relative_to(ROOT).as_posix(),
            "SHA-256": hashlib.sha256(path.read_bytes()).hexdigest(),
        } for path in input_paths])
        readable_table(receipt)
        package_versions = {name: version(name) for name in ["pandas", "numpy", "matplotlib", "nbformat", "nbclient"]}
        readable_table(pd.DataFrame([package_versions]))
        expected_figures = ((4 if not selected_audio.empty else 3) + int(history_figure_created)
                            + int(storytel_genre_figure_created) + int(storytel_moment_figure_created))
        expected_figures += extra_industry_figures
        assert len(figure_paths) == expected_figures
        assert all(path.is_file() and path.stat().st_size > 10_000 for path in figure_paths)
        assert not selected_audio.period.isna().any()
        display(Markdown(f"**Run complete:** all input, metric and dashboard-row checks passed. "
                         f"{len(figure_paths)} native analytical figures were retained inline and saved in `outputs/audiobook_figures/`. "
                         "Commercial, comparability and survey-design limitations remain as stated above."))
        """),
    ]
    nbformat.validate(notebook)
    return notebook


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--no-execute", action="store_true")
    arguments = parser.parse_args()
    default_root = Path(__file__).resolve().parents[1]
    project_root = (arguments.project_root or default_root).resolve()
    output_root = (arguments.output_root or default_root).resolve()
    notebook_dir = output_root / "notebooks"
    output_dir = output_root / "outputs"
    notebook_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    local_environment = {
        "JUPYTER_CONFIG_DIR": output_root / "work/jupyter/config",
        "JUPYTER_DATA_DIR": output_root / "work/jupyter/data",
        "JUPYTER_RUNTIME_DIR": output_root / "work/jupyter/runtime",
        "IPYTHONDIR": output_root / "work/ipython",
        "MPLCONFIGDIR": output_root / "work/matplotlib",
        "XDG_CACHE_HOME": output_root / "work/cache",
        "GRA_PROJECT_ROOT": project_root,
        "GRA_NOTEBOOK_OUTPUT_ROOT": output_root,
    }
    for name, value in local_environment.items():
        os.environ[name] = str(value)
        if not name.startswith("GRA_"):
            Path(value).mkdir(parents=True, exist_ok=True)
    notebook = make_notebook(project_root)
    path = notebook_dir / "02_audiobook_market_check.ipynb"
    nbformat.write(notebook, path)
    if arguments.no_execute:
        print(f"Saved validated draft notebook: {path}")
        return
    manager = KernelManager(kernel_name="python3", connection_file=str(output_root / "work/jupyter/runtime/kernel-audiobook.json"))
    manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
    client = NotebookClient(notebook, km=manager, timeout=180, resources={"metadata": {"path": str(project_root)}})
    try:
        client.execute()
    finally:
        if manager.has_kernel:
            manager.shutdown_kernel(now=True)
    nbformat.validate(notebook)
    nbformat.write(notebook, path)
    style = """
      body { background: #f5f7f8; color: #24333c; }
      main { max-width: 1180px; margin: 24px auto; padding: 28px 46px; background: white; }
      h1 { font-size: 42px !important; letter-spacing: -1.2px; color: #1c425a; }
      h2 { color: #1c425a; border-top: 1px solid #dfe7eb; padding-top: 24px; margin-top: 36px !important; }
      h3 { color: #24333c; }
      p, li { line-height: 1.65; }
      a { color: #25658c; }
      .jp-RenderedHTMLCommon table { font-size: 12px; width: 100%; table-layout: fixed; }
      .jp-RenderedHTMLCommon th { text-align: left; background: #edf3f6; padding: 10px 12px; overflow-wrap: anywhere; }
      .jp-RenderedHTMLCommon td { text-align: left; padding: 9px 12px; white-space: normal; overflow-wrap: anywhere; }
      .jp-InputArea-editor { border: 1px solid #e7edf0; border-radius: 5px; font-size: 12px; }
      .jp-RenderedImage img { max-width: 100%; height: auto; }
      @media (max-width: 720px) { main { margin: 0; padding: 14px 16px; } h1 { font-size: 32px !important; } }
    """
    html_path = output_dir / "audiobook_notebook.html"
    export_notebook_html(notebook, html_path, style)
    images = sum("image/png" in output.get("data", {}) for cell in notebook.cells for output in cell.get("outputs", []))
    print(f"Saved executed notebook: {path}")
    print(f"Saved portable HTML: {html_path}")
    print(f"Executed {sum(cell.cell_type == 'code' for cell in notebook.cells)} code cells; retained {images} inline PNG outputs.")


if __name__ == "__main__":
    main()
