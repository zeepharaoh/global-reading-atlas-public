"""Regression checks for portable, passive notebook reports."""
import importlib.util
from pathlib import Path

import nbformat
import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("portable_html", ROOT / "notebooks/portable_html.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def notebook_with_output(data):
    notebook = nbformat.v4.new_notebook()
    notebook.cells = [nbformat.v4.new_code_cell("result", outputs=[nbformat.v4.new_output(
        output_type="display_data", data=data,
    )])]
    return notebook


def test_export_retains_sources_tables_and_embedded_figures_without_scripts(tmp_path):
    png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aGZkAAAAASUVORK5CYII="
    notebook = notebook_with_output({"image/png": png, "text/plain": "A source backed figure"})
    notebook.cells.insert(0, nbformat.v4.new_markdown_cell("# Findings\n\n[Original evidence](https://example.org/report)"))
    notebook.cells.append(nbformat.v4.new_code_cell("table", outputs=[nbformat.v4.new_output(
        output_type="display_data", data={"text/html": "<table><tr><th>Year</th><th>Reach</th></tr>"
        "<tr><td>2025</td><td>15%</td></tr></table>", "text/plain": "2025: 15%"},
    )]))
    path = tmp_path / "report.html"
    MODULE.export_notebook_html(notebook, path, "body { color: #24333c; }")
    html = path.read_text()
    assert '<script' not in html.lower()
    assert '<table>' in html and '<td>15%</td>' in html
    assert f'src="data:image/png;base64,{png}"' in html
    assert 'href="https://example.org/report"' in html
    assert 'Content-Security-Policy' in html
    assert "script-src 'none'" in html
    assert 'name="referrer"' in html and 'content="no-referrer"' in html
    assert "color: #24333c" in html


@pytest.mark.parametrize("active_html", [
    '<script src="https://example.org/widget.js"></script>',
    '<script>alert(1)</script>',
    '<img src="https://example.org/tracker.png">',
    '<img src="data:image/png;base64,AAAA" onerror="alert(1)">',
    '<img src="data:image/png;base64,AAAA" srcset="https://example.org/large.png 2x">',
    '<iframe src="https://example.org/widget"></iframe>',
    '<object data="https://example.org/widget"></object>',
    '<svg><script>alert(1)</script></svg>',
    '<meta http-equiv="refresh" content="0;url=https://example.org">',
    '<meta http-equiv="refresh" http-equiv="Content-Security-Policy" content="0;url=https://example.org">',
    '<a href="java&#115;cript:alert(1)">Source</a>',
    '<style>@import "https://example.org/theme.css";</style>',
    '<style>div { background: url(https://example.org/tracker.png) }</style>',
    '<style>div { background: url("https://example.org/tracker.png") }</style>',
    '<style>div { background: u\\72l("https://example.org/tracker.png") }</style>',
    '<style>div { background: image-set("https://example.org/tracker.png" 1x) }</style>',
    '<div style="background: url(//example.org/tracker.png)">Data</div>',
    '<form action="https://example.org"><input name="data"></form>',
])
def test_active_or_external_html_fails_without_replacing_last_report(tmp_path, active_html):
    path = tmp_path / "report.html"
    path.write_text("Last validated report")
    notebook = notebook_with_output({"text/html": active_html, "text/plain": "fallback"})
    with pytest.raises(ValueError):
        MODULE.export_notebook_html(notebook, path, "")
    assert path.read_text() == "Last validated report"


@pytest.mark.parametrize("mime, value", [
    ("application/javascript", "alert(1)"),
    ("application/vnd.jupyter.widget-view+json", {"model_id": "example"}),
    ("text/vnd.mermaid", "graph LR; A-->B"),
    ("image/svg+xml", "<svg></svg>"),
    ("text/latex", "$x^2$"),
])
def test_unsupported_rich_outputs_are_not_silently_replaced_with_text(tmp_path, mime, value):
    notebook = notebook_with_output({mime: value, "text/plain": "fallback"})
    with pytest.raises(ValueError, match="PNG or table"):
        MODULE.export_notebook_html(notebook, tmp_path / "report.html", "")
    assert not (tmp_path / "report.html").exists()


def test_widget_state_requires_an_explicit_static_replacement(tmp_path):
    notebook = nbformat.v4.new_notebook(metadata={"widgets": {"application/vnd.jupyter.widget-state+json": {}}})
    with pytest.raises(ValueError, match="widget state"):
        MODULE.export_notebook_html(notebook, tmp_path / "report.html", "")


def test_raw_cells_cannot_hide_unsupported_markup(tmp_path):
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_raw_cell("<script>alert(1)</script>")])
    with pytest.raises(ValueError, match="raw cells"):
        MODULE.export_notebook_html(notebook, tmp_path / "report.html", "")


def test_active_markdown_and_css_are_checked_after_rendering(tmp_path):
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell("![Tracking](https://example.org/pixel.png)")])
    with pytest.raises(ValueError, match="images must be embedded"):
        MODULE.export_notebook_html(notebook, tmp_path / "report.html", "")
    with pytest.raises(ValueError, match="embedded images"):
        MODULE.export_notebook_html(nbformat.v4.new_notebook(), tmp_path / "report.html", "body { background: url('https://example.org/a.png') }")


def test_report_validator_requires_static_content_policy():
    with pytest.raises(ValueError, match="content policy"):
        MODULE.validate_static_html("<html><body><p>Looks passive but lacks a policy</p></body></html>")


@pytest.mark.parametrize("name", ["notebook.html", "audiobook_notebook.html"])
def test_published_notebook_reports_are_static(name):
    MODULE.validate_static_html((ROOT / "outputs" / name).read_text(encoding="utf-8"))
