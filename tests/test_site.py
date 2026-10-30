"""Publish only reviewed artifacts and reject a broken dashboard package."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_site", ROOT / "scripts/build_site.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    snapshot = b'{"queries":{"formats":{"rows":[]}}}'
    digest = hashlib.sha256(snapshot).hexdigest()
    snapshot_name = f"snapshot.{digest}.json"
    html = f'<meta name="data-app-local-snapshot" content="{snapshot_name}">'.encode()
    dist = root / "dashboard/dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_bytes(html)
    (dist / snapshot_name).write_bytes(snapshot)
    manifest = {
        "version": 1,
        "kind": "separate-data-v1",
        "html": {"path": "index.html", "sha256": hashlib.sha256(html).hexdigest(), "bytes": len(html)},
        "snapshot": {"path": snapshot_name, "sha256": digest, "bytes": len(snapshot)},
        "sourceSnapshotSha256": digest,
    }
    (dist / "data-app-build.json").write_text(json.dumps(manifest))
    for name in (
        "site/index.html", "outputs/notebook.html", "outputs/audiobook_notebook.html",
        "outputs/coverage_map.png", "notebooks/01_reading_and_listening_analysis.ipynb",
        "notebooks/02_audiobook_market_check.ipynb", "data/source_register.json",
        "THIRD_PARTY_NOTICES.txt",
    ):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("reviewed artifact")
    return root


def test_package_has_an_explicit_allowlist_and_keeps_dashboard_bytes(project, tmp_path):
    for name in (".git/config", ".env", ".idea/workspace.xml", "data/raw/source.pdf", "dashboard/dist/secret.txt"):
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("must never be published")
    output = tmp_path / "public-site"
    receipt = MODULE.build_site(project, output)
    assert len(receipt["files"]) == 12
    assert set(path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()) == (
        set(receipt["files"]) | {"site-build.json"}
    )
    for path in (project / "dashboard/dist").iterdir():
        if path.name != "secret.txt":
            assert (output / "dashboard" / path.name).read_bytes() == path.read_bytes()
    assert (output / "THIRD_PARTY_NOTICES.txt").read_bytes() == (project / "THIRD_PARTY_NOTICES.txt").read_bytes()
    assert (output / "dashboard/THIRD_PARTY_NOTICES.txt").read_bytes() == (project / "THIRD_PARTY_NOTICES.txt").read_bytes()
    assert not any("must never be published" in path.read_text() for path in output.rglob("*") if path.is_file())
    assert MODULE.build_site(project, output) == receipt


@pytest.mark.parametrize("alteration", ["tampered_snapshot", "missing_snapshot", "wrong_reference", "unsafe_path"])
def test_invalid_dashboard_fails_before_changing_existing_output(project, tmp_path, alteration):
    output = tmp_path / "public-site"
    original = MODULE.build_site(project, output)
    dist = project / "dashboard/dist"
    snapshot = next(dist.glob("snapshot.*.json"))
    if alteration == "tampered_snapshot":
        snapshot.write_text('{"queries":{"changed":{}}}')
    elif alteration == "missing_snapshot":
        snapshot.unlink()
    elif alteration == "wrong_reference":
        html = b'<meta name="data-app-local-snapshot" content="other.json">'
        (dist / "index.html").write_bytes(html)
        path = dist / "data-app-build.json"
        manifest = json.loads(path.read_text())
        manifest["html"].update(sha256=hashlib.sha256(html).hexdigest(), bytes=len(html))
        path.write_text(json.dumps(manifest))
    else:
        path = dist / "data-app-build.json"
        manifest = json.loads(path.read_text())
        manifest["snapshot"]["path"] = "../../private.json"
        path.write_text(json.dumps(manifest))
    with pytest.raises((ValueError, FileNotFoundError)):
        MODULE.build_site(project, output)
    assert json.loads((output / "site-build.json").read_text()) == original


def test_unrelated_output_and_source_directories_are_protected(project, tmp_path):
    output = tmp_path / "public-site"
    output.mkdir()
    personal = output / "personal.txt"
    personal.write_text("keep")
    with pytest.raises(ValueError, match="non-empty directory"):
        MODULE.build_site(project, output)
    assert personal.read_text() == "keep"
    with pytest.raises(ValueError, match="source directories"):
        MODULE.build_site(project, project / "dashboard/published")
    MODULE.build_site(project, tmp_path / "clean-site")
    (tmp_path / "clean-site/unrelated.txt").write_text("keep")
    with pytest.raises(ValueError, match="unrelated files"):
        MODULE.build_site(project, tmp_path / "clean-site")


@pytest.mark.parametrize("directory", [".git", ".venv", ".private"])
def test_hidden_project_directories_are_never_publication_targets(project, directory):
    protected = project / directory
    protected.mkdir()
    marker = protected / "keep.txt"
    marker.write_text("keep")
    with pytest.raises(ValueError, match="hidden project directories"):
        MODULE.build_site(project, protected / "preview")
    assert marker.read_text() == "keep"
    assert not (protected / "preview").exists()


def set_inline_build(project, declared_hash=None, local_reference=False):
    dist = project / "dashboard/dist"
    path = dist / "data-app-build.json"
    manifest = json.loads(path.read_text())
    digest = manifest["snapshot"]["sha256"]
    html = f'<meta name="data-app-snapshot-sha256" content="{declared_hash or digest}">'
    if local_reference:
        html += f'<meta name="data-app-local-snapshot" content="{manifest["snapshot"]["path"]}">'
    html = html.encode()
    (dist / "index.html").write_bytes(html)
    manifest["kind"] = "inline-data-v1"
    manifest["html"].update(sha256=hashlib.sha256(html).hexdigest(), bytes=len(html))
    path.write_text(json.dumps(manifest))


def test_inline_dashboard_preserves_the_exact_source_snapshot(project, tmp_path):
    set_inline_build(project)
    receipt = MODULE.build_site(project, tmp_path / "public-site")
    assert len(receipt["files"]) == 12
    assert MODULE.validate_dashboard(tmp_path / "public-site/dashboard") == next(
        (project / "dashboard/dist").glob("snapshot.*.json")
    ).name


@pytest.mark.parametrize("alteration", ["declared_hash", "snapshot_bytes", "source_hash", "mixed_reference"])
def test_inline_dashboard_rejects_mismatched_evidence(project, tmp_path, alteration):
    set_inline_build(
        project, declared_hash="0" * 64 if alteration == "declared_hash" else None,
        local_reference=alteration == "mixed_reference",
    )
    dist = project / "dashboard/dist"
    if alteration == "snapshot_bytes":
        next(dist.glob("snapshot.*.json")).write_text('{"queries":{"different":{}}}')
    elif alteration == "source_hash":
        path = dist / "data-app-build.json"
        manifest = json.loads(path.read_text())
        manifest["sourceSnapshotSha256"] = "0" * 64
        path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        MODULE.build_site(project, tmp_path / "public-site")
    assert not (tmp_path / "public-site").exists()
