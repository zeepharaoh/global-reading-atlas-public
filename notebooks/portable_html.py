"""Export static notebook reports without browser scripts or external assets."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import nbformat
import tinycss2
from nbconvert import HTMLExporter


CONTENT_POLICY = (
    "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; "
    "img-src data:; font-src data:; connect-src 'none'; object-src 'none'; "
    "base-uri 'none'; form-action 'none'"
)
STATIC_TEMPLATE = """{% extends 'lab/index.html.j2' %}
{% block html_head_js %}
<meta http-equiv="Content-Security-Policy" content="{{ resources.content_policy }}">
<meta name="referrer" content="no-referrer">
{% endblock html_head_js %}
{% block html_head_js_mathjax %}{% endblock html_head_js_mathjax %}
{% block html_head_js_mermaidjs %}{% endblock html_head_js_mermaidjs %}
{% block jupyter_widgets %}{% endblock jupyter_widgets %}
{% block html_head_css %}<style>{{ resources.report_style }}</style>{% endblock html_head_css %}
{% block footer %}</html>{% endblock footer %}
"""
STATIC_MIMES = {"text/plain", "text/markdown", "text/html", "image/png", "image/jpeg"}
STATIC_TAGS = set(
    "html head title meta style body main article header footer section nav div span p "
    "h1 h2 h3 h4 h5 h6 a img figure figcaption code pre blockquote ul ol li dl dt dd "
    "strong em b i s u sub sup kbd samp var br hr table caption colgroup col thead tbody "
    "tfoot tr th td abbr address small time mark details summary".split()
)
STATIC_ATTRIBUTES = {
    "class", "id", "title", "lang", "dir", "role", "tabindex", "style",
    "href", "target", "rel", "src", "alt", "width", "height", "charset", "name",
    "content", "http-equiv", "type", "border", "cellspacing", "cellpadding",
    "rowspan", "colspan", "scope", "align", "valign", "nowrap", "start", "value",
    "reversed", "datetime", "open",
}


def _embedded_image(value: str) -> bool:
    return value.strip().lower().startswith((
        "data:image/png;base64,", "data:image/jpeg;base64,", "data:image/svg+xml;base64,",
    ))


def _validate_css(css: str) -> None:
    def inspect(tokens):
        for token in tokens:
            if token.type == "error":
                raise ValueError("Notebook report contains invalid CSS.")
            if token.type == "at-keyword" and token.value.lower() in {"import", "namespace"}:
                raise ValueError("Notebook report CSS cannot import external resources.")
            if token.type == "url" and not _embedded_image(token.value):
                raise ValueError("Notebook report CSS must use embedded images only.")
            if token.type == "string" and (
                token.value.strip().startswith("//")
                or urlsplit(token.value.strip()).scheme.lower() in {"http", "https"}
            ):
                raise ValueError("Notebook report CSS cannot reference external assets.")
            if token.type == "function":
                if token.lower_name == "expression":
                    raise ValueError("Notebook report CSS cannot contain executable expressions.")
                if token.lower_name == "url":
                    values = [item for item in token.arguments if item.type not in {"whitespace", "comment"}]
                    if len(values) != 1 or values[0].type != "string" or not _embedded_image(values[0].value):
                        raise ValueError("Notebook report CSS must use embedded images only.")
                inspect(token.arguments)
            if getattr(token, "content", None) is not None:
                inspect(token.content)

    inspect(tinycss2.parse_component_value_list(css))


class _StaticReportParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_style = False
        self.style_parts = []
        self.policy_found = False

    def handle_starttag(self, tag, attributes):
        if tag not in STATIC_TAGS:
            raise ValueError(f"Notebook report contains unsupported active or rich HTML: {tag}.")
        attrs = dict(attributes)
        if len(attrs) != len(attributes):
            raise ValueError("Notebook report contains ambiguous duplicate HTML attributes.")
        for name, value in attributes:
            if name not in STATIC_ATTRIBUTES and not name.startswith(("aria-", "data-")):
                raise ValueError(f"Notebook report contains an unsupported HTML attribute: {name}.")
            if name == "style":
                _validate_css(value or "")
            if name == "href":
                href = (value or "").strip()
                if tag != "a" or not (
                    href.startswith("#") or urlsplit(href).scheme.lower() in {"http", "https", "mailto"}
                ):
                    raise ValueError("Notebook report allows source hyperlinks only.")
            if name == "src" and (tag != "img" or not _embedded_image(value or "")):
                raise ValueError("Notebook report images must be embedded.")
        if tag == "meta" and "http-equiv" in attrs:
            if (attrs["http-equiv"] or "").lower() != "content-security-policy" or attrs.get("content") != CONTENT_POLICY:
                raise ValueError("Notebook report contains an unsupported browser policy or redirect.")
            self.policy_found = True
        if tag == "style":
            self.in_style = True
            self.style_parts = []

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if tag == "style":
            self.in_style = False
            _validate_css("".join(self.style_parts))

    def handle_data(self, data):
        if self.in_style:
            self.style_parts.append(data)


def validate_static_html(html: str) -> None:
    """Reject scripts, automatic external loads and unsupported rich markup."""
    parser = _StaticReportParser()
    parser.feed(html)
    parser.close()
    if not parser.policy_found or parser.in_style:
        raise ValueError("Notebook report is missing its complete static content policy.")


def export_notebook_html(notebook, path: Path, report_style: str) -> None:
    """Write a validated report, preserving an existing report on export failure."""
    nbformat.validate(notebook)
    if notebook.metadata.get("widgets"):
        raise ValueError("Static notebook reports cannot export live widget state.")
    for cell in notebook.cells:
        if cell.cell_type == "raw" and cell.source.strip():
            raise ValueError("Static notebook reports cannot export unrendered raw cells.")
        for output in cell.get("outputs", []):
            unsupported = set(output.get("data", {})) - STATIC_MIMES
            if unsupported:
                raise ValueError(f"Static notebook reports need a PNG or table instead of {sorted(unsupported)}.")
    exporter = HTMLExporter(
        template_name="lab", raw_template=STATIC_TEMPLATE,
        exclude_input_prompt=True, exclude_output_prompt=True,
    )
    html, _ = exporter.from_notebook_node(notebook, resources={
        "content_policy": CONTENT_POLICY, "report_style": report_style,
    })
    validate_static_html(html)
    Path(path).write_text(html, encoding="utf-8")
