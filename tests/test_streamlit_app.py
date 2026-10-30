"""Exercise the Streamlit companion against the reviewed local snapshot."""

from io import BytesIO
import json
from pathlib import Path

import pandas as pd
import pytest

streamlit = pytest.importorskip("streamlit")
AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_app.py"
SNAPSHOT = ROOT / "data/processed/dashboard_snapshot.json"


@pytest.fixture(scope="module", autouse=True)
def reviewed_input_stays_unchanged():
    original = SNAPSHOT.read_bytes()
    yield
    assert SNAPSHOT.read_bytes() == original


@pytest.fixture
def app():
    return AppTest.from_file(str(APP), default_timeout=20).run()


def widget(elements, label):
    return next(element for element in elements if element.label == label)


def test_all_six_pages_render_reviewed_tables_and_charts(app):
    titles = {
        "Audiobooks": "Audiobooks", "Industry": "Book industry",
        "Reading": "Book participation", "Formats": "Paper books, ebooks and audiobooks",
        "Genres": "Genres", "Coverage": "Evidence coverage",
    }
    for page, expected_title in titles.items():
        app.radio(key="atlas_page").set_value(page).run()
        assert not app.exception
        assert app.title[0].value == expected_title
        assert len(app.dataframe) > 0
        assert len(app.get("vega_lite_chart")) > 0


def test_default_audio_chart_uses_exact_four_sweden_observations(app):
    import pyarrow as pa

    assert not app.exception
    assert app.selectbox(key="audio_country").value == "Sweden"
    rows = app.dataframe[0].value
    assert rows["Observation year"].tolist() == [2022, 2023, 2024, 2025]
    assert rows["Reported percentage"].tolist() == [14.0, 15.0, 15.0, 15.0]
    assert rows["Country code"].eq("SWE").all()
    chart = app.get("vega_lite_chart")[0]
    plotted = pa.ipc.open_stream(chart.proto.datasets[0].data.data).read_all().to_pandas()
    assert plotted["year"].tolist() == rows["Observation year"].tolist()
    assert plotted["participation"].tolist() == rows["Reported percentage"].tolist()
    assert app.metric[0].value == "15.0%"
    assert app.metric[1].value == "2025"


def test_unpublished_2026_has_no_national_audio_values(app):
    app.slider(key="atlas_years").set_value((2026, 2026)).run()
    assert not app.exception
    assert app.dataframe[0].value.empty
    assert len(app.metric) == 0
    assert any("Unpublished years are not estimated" in element.value for element in app.info)
    assert app.dataframe[1].value["Observation year"].eq(2026).all()
    assert app.dataframe[1].value["Source ID"].eq("storytel_story_report_2026").all()


def test_canadian_genre_missing_value_stays_visible_in_source_rows(app):
    app.radio(key="atlas_page").set_value("Genres").run()
    app.selectbox(key="genres_year").set_value(2024).run()
    assert not app.exception
    assert app.selectbox(key="genres_country").value == "Canada"
    assert app.selectbox(key="genres_format").value == "Audiobook"
    rows = app.dataframe[0].value
    comics = rows.loc[rows["Genre"].eq("Comics or Graphic Novels")]
    assert len(comics) == 1
    assert comics["Reported percentage"].isna().all()
    assert any("Unavailable observations stay missing" in element.value for element in app.caption)
    assert rows["Country code"].eq("CAN").all()
    assert rows["Observation year"].eq(2024).all()


def test_audiobooks_shows_evidence_without_country_decision_panels(app):
    assert not app.exception
    assert "Research route" not in [element.label for element in app.radio]
    assert "Storytel country case studies" not in [element.label for element in app.get("expander")]
    assert app.selectbox(key="listener_country").value == "Sweden"
    assert not any("Decision route" in element.value.columns for element in app.dataframe)
    assert len(app.get("vega_lite_chart")) >= 2


@pytest.mark.parametrize("page,kind,label,changed,default", [
    ("Industry", "selectbox", "Format in company register", "Print", "All"),
    ("Industry", "selectbox", "Country", "Sweden", "United States"),
    ("Reading", "selectbox", "Geography", "EU members", "All surveyed countries"),
    ("Reading", "selectbox", "Demographic group", "Education", "Age"),
    ("Coverage", "selectbox", "Audit status", "Data extracted", "All"),
])
def test_reset_restores_page_filter_defaults(app, page, kind, label, changed, default):
    app.radio(key="atlas_page").set_value(page).run()
    widget(app.get(kind), label).set_value(changed).run()
    widget(app.button, "Reset filters").click().run()
    assert not app.exception
    assert app.radio(key="atlas_page").value == page
    assert widget(app.get(kind), label).value == default


def test_source_panel_and_download_are_exact_selected_rows(monkeypatch):
    captured = {}
    original_download = streamlit.download_button

    def capture_download(*args, **kwargs):
        if kwargs.get("key"):
            captured[kwargs["key"]] = kwargs.get("data", args[1] if len(args) > 1 else None)
        return original_download(*args, **kwargs)

    monkeypatch.setattr(streamlit, "download_button", capture_download)
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    app.selectbox(key="audio_country").set_value("Canada").run()
    assert not app.exception
    snapshot = json.loads(SNAPSHOT.read_text())
    expected = pd.DataFrame([
        row for row in snapshot["queries"]["audiobook_history"]["rows"]
        if row["country_iso3"] == "CAN"
    ])
    downloaded = pd.read_csv(BytesIO(captured["audio_history_download"]))
    pd.testing.assert_frame_equal(downloaded, expected)
    source = json.loads(app.json[0].value)
    assert source["source"] == snapshot["queries"]["audiobook_history"]["source"]
    assert source["methods"] == snapshot["queries"]["audiobook_history"]["methods"]
    displayed = app.dataframe[0].value
    assert displayed["Observation year"].tolist() == expected["year"].tolist()
    assert displayed["Reported percentage"].tolist() == expected["participation"].tolist()
    assert displayed["Original source"].tolist() == expected["source_url"].tolist()
    assert displayed["Survey base"].tolist() == expected["denominator"].tolist()


def test_genres_country_list_includes_every_reviewed_genre_country(app):
    snapshot = json.loads(SNAPSHOT.read_text())
    app.radio(key="atlas_page").set_value("Genres").run()
    expected = snapshot["queries"]["genre_history"]["rows"] + [
        row for row in snapshot["queries"]["storytel_audio_2026"]["rows"]
        if row["record_type"] == "genre"
    ]
    expected_countries = sorted({row["country"] for row in expected})
    assert len(expected_countries) == 14
    assert app.selectbox(key="genres_country").options == expected_countries
    for country in expected_countries:
        app.selectbox(key="genres_country").set_value(country).run()
        assert not app.exception
        rows = app.dataframe[0].value
        assert not rows.empty
        assert rows["Country"].eq(country).all()
        assert rows["Source ID"].nunique() == 1
        assert rows["Observation year"].nunique() == 1
        if "Record type" in rows:
            assert rows["Record type"].eq("genre").all()
        source = json.loads(app.json[0].value)
        query_id = "storytel_audio_2026" if country in {
            "Bulgaria", "Finland", "Norway", "Poland", "Sweden",
        } else "genre_history"
        assert source["source"] == snapshot["queries"][query_id]["source"]
        assert len(app.get("vega_lite_chart")) == 1


def test_france_genre_sources_keep_reader_and_listener_bases_separate(app):
    app.radio(key="atlas_page").set_value("Genres").run()
    app.selectbox(key="genres_country").set_value("France").run()
    assert len(app.selectbox(key="genres_source").options) == 2
    for source_id, expected_count, expected_format in [
        ("cnl_fr", 19, "Paper or digital"),
        ("audible_compass_2025", 5, "Audiobook"),
    ]:
        app.selectbox(key="genres_source").set_value(source_id).run()
        assert not app.exception
        rows = app.dataframe[0].value
        assert rows["Source ID"].eq(source_id).all()
        assert rows["Format"].eq(expected_format).all()
        assert len(rows) == expected_count


def test_sweden_genres_retain_listener_study_definitions(app):
    app.radio(key="atlas_page").set_value("Genres").run()
    app.selectbox(key="genres_country").set_value("Sweden").run()
    assert not app.exception
    rows = app.dataframe[0].value
    assert rows["Country code"].eq("SWE").all()
    assert rows["Observation year"].eq(2026).all()
    assert rows["Record type"].eq("genre").all()
    assert rows["Source ID"].eq("storytel_story_report_2026").all()
    assert len(rows) == 5
    assert any("Latest available observation: 2026" in item.value for item in app.caption)
    assert any("not national reach or Storytel customers" in item.value for item in app.caption)


def test_genres_2026_filter_explains_missing_reader_year_and_keeps_listener_data(app):
    app.radio(key="atlas_page").set_value("Genres").run()
    assert any("Latest available observation: 2025" in item.value for item in app.caption)
    app.slider(key="atlas_years").set_value((2026, 2026)).run()
    assert not app.exception
    assert app.dataframe[0].value.empty
    assert len(app.get("vega_lite_chart")) == 0
    assert any("No reviewed observation for 2026" in item.value for item in app.info)
    assert any("Latest available observation: 2025" in item.value for item in app.caption)
    app.selectbox(key="genres_country").set_value("Sweden").run()
    assert not app.exception
    assert app.dataframe[0].value["Observation year"].eq(2026).all()
    assert len(app.dataframe[0].value) == 5
    assert not any("No reviewed observation for 2026" in item.value for item in app.info)


def test_listener_study_does_not_backfill_selected_2025(app):
    app.radio(key="atlas_page").set_value("Genres").run()
    app.selectbox(key="genres_country").set_value("Sweden").run()
    app.slider(key="atlas_years").set_value((2025, 2025)).run()
    assert not app.exception
    assert app.dataframe[0].value.empty
    assert len(app.get("vega_lite_chart")) == 0
    assert any("Latest available observation: 2026" in item.value for item in app.caption)
    assert any("No reviewed observation for 2025" in item.value for item in app.info)


def test_genre_listener_download_excludes_listening_moments(monkeypatch):
    captured = {}
    original_download = streamlit.download_button

    def capture_download(*args, **kwargs):
        if kwargs.get("key"):
            captured[kwargs["key"]] = kwargs.get("data", args[1] if len(args) > 1 else None)
        return original_download(*args, **kwargs)

    monkeypatch.setattr(streamlit, "download_button", capture_download)
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    app.radio(key="atlas_page").set_value("Genres").run()
    app.selectbox(key="genres_country").set_value("Sweden").run()
    app.selectbox(key="genres_country").set_value("Bulgaria").run()
    assert not app.exception
    snapshot = json.loads(SNAPSHOT.read_text())
    expected = pd.DataFrame([
        row for row in snapshot["queries"]["storytel_audio_2026"]["rows"]
        if row["country_iso3"] == "BGR" and row["record_type"] == "genre"
    ])
    downloaded = pd.read_csv(BytesIO(captured["genres_download"]))
    pd.testing.assert_frame_equal(
        downloaded.astype(object).where(downloaded.notna(), None), expected.astype(object),
    )
    assert app.dataframe[0].value["Record type"].eq("genre").all()


def test_industry_country_and_revenue_controls_show_all_reviewed_series(app):
    snapshot = json.loads(SNAPSHOT.read_text())
    expected = pd.DataFrame(snapshot["queries"]["industry_metrics"]["rows"])
    app.radio(key="atlas_page").set_value("Industry").run()
    assert app.selectbox(key="industry_country").options == sorted(expected.country.unique())
    assert expected.country.nunique() > 2
    assert app.selectbox(key="industry_series").value == "us_apa_audiobook_revenue"
    for country in sorted(expected.country.unique()):
        app.selectbox(key="industry_country").set_value(country).run()
        available = expected.loc[expected.country.eq(country)]
        assert set(app.selectbox(key="industry_series").options) == set(available.metric)
        for series in available.series_id.unique():
            app.selectbox(key="industry_series").set_value(series).run()
            assert not app.exception
            rows = app.dataframe[0].value
            selected = expected.loc[expected.series_id.eq(series)]
            assert rows["Country"].eq(country).all()
            assert rows["Series id"].eq(series).all()
            assert rows["Value"].tolist() == selected.value.tolist()
            assert rows["Unit"].tolist() == selected.unit.tolist()
            assert rows["Original source"].tolist() == selected.source_url.tolist()
            assert rows["Publication date"].tolist() == selected.publication_date.tolist()
            assert any("Published book industry money figures" in item.value for item in app.caption)


def test_industry_unpublished_2026_revenue_is_not_estimated(app):
    app.radio(key="atlas_page").set_value("Industry").run()
    app.selectbox(key="industry_country").set_value("United Kingdom").run()
    app.slider(key="atlas_years").set_value((2026, 2026)).run()
    assert not app.exception
    assert app.dataframe[0].value.empty
    assert len(app.get("vega_lite_chart")) == 0
    assert any("No reviewed observation for 2026" in item.value for item in app.info)
    assert any("Latest available observation: 2025" in item.value for item in app.caption)


def test_coverage_map_uses_local_geometry_and_exact_filtered_evidence(app):
    snapshot = json.loads(SNAPSHOT.read_text())
    expected = pd.DataFrame(snapshot["queries"]["coverage"]["rows"])
    app.radio(key="atlas_page").set_value("Coverage").run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 249
    assert "SGP" in set(app.dataframe[0].value["Country code"])
    context_before = None
    for status in ["All", "Data extracted", "Not researched", "All"]:
        app.selectbox(key="coverage_status_filter").set_value(status).run()
        assert not app.exception
        spec = json.loads(app.get("vega_lite_chart")[0].proto.spec)
        assert all(layer["mark"]["type"] == "geoshape" for layer in spec["layer"])
        assert not any("url" in layer["data"] for layer in spec["layer"])
        context = spec["datasets"][spec["layer"][0]["data"]["name"]]
        selected = spec["datasets"][spec["layer"][1]["data"]["name"]]
        if context_before is None:
            context_before = context
        assert context == context_before
        source_rows = expected if status == "All" else expected.loc[expected.audit_status.eq(status)]
        assert len(app.dataframe[0].value) == len(source_rows)
        assert set(app.dataframe[0].value["Country code"]) == set(source_rows.country_iso3)
        keyed = source_rows.set_index("country_iso3").to_dict(orient="index")
        assert selected["features"]
        for feature in selected["features"]:
            properties = feature["properties"]
            code = properties["country_iso3"]
            assert properties == {"country_iso3": code, **keyed[code]}
            if status != "All":
                assert properties["audit_status"] == status


@pytest.mark.parametrize("selection,report_name,notebook_name", [
    ("Audiobook market analysis", "audiobook_notebook.html", "02_audiobook_market_check.ipynb"),
    ("Reading and listening analysis", "notebook.html", "01_reading_and_listening_analysis.ipynb"),
])
def test_reports_render_inside_streamlit_with_exact_downloads(monkeypatch, selection, report_name, notebook_name):
    captured = {}
    original_download = streamlit.download_button

    def capture_download(*args, **kwargs):
        if kwargs.get("key"):
            captured[kwargs["key"]] = kwargs.get("data", args[1] if len(args) > 1 else None)
        return original_download(*args, **kwargs)

    monkeypatch.setattr(streamlit, "download_button", capture_download)
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    app.radio(key="atlas_page").set_value("Reports").run()
    app.selectbox(key="report_choice").set_value(selection).run()
    assert not app.exception
    assert len(app.slider) == 0
    frames = app.get("iframe")
    assert len(frames) == 1
    report = (ROOT / "outputs" / report_name).read_bytes()
    assert frames[0].proto.src == ""
    assert frames[0].proto.srcdoc == report.decode("utf-8")
    assert frames[0].proto.alt == f"{selection} report"
    assert "script-src 'none'" in frames[0].proto.srcdoc
    assert captured["report_html_download"] == report
    assert captured["report_notebook_download"] == (ROOT / "notebooks" / notebook_name).read_bytes()
    assert not any("github.io" in element.proto.url for element in app.sidebar.get("link_button"))
