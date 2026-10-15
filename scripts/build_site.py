"""Package the reviewed dashboard and reports for a static website."""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import tempfile


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = "site-build.json"
KIND = "global-reading-atlas-static-site-v1"
SHA256 = re.compile(r"[0-9a-f]{64}")
SNAPSHOT = re.compile(r"snapshot\.([0-9a-f]{64})\.json")


class SnapshotMetadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []
        self.hashes = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "meta" and attributes.get("name") == "data-app-local-snapshot":
            self.paths.append(attributes.get("content"))
        if tag == "meta" and attributes.get("name") == "data-app-snapshot-sha256":
            self.hashes.append(attributes.get("content"))


def checked_bytes(path: Path, metadata: dict) -> bytes:
    """Read an artifact only after its declared size and SHA256 agree."""
    digest = metadata.get("sha256", "")
    size = metadata.get("bytes")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise ValueError(f"Invalid SHA256 in build manifest: {path.name}")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise ValueError(f"Invalid byte length in build manifest: {path.name}")
    data = path.read_bytes()
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f"Build artifact failed integrity validation: {path.name}")
    return data


def validate_dashboard(dist: Path) -> str:
    """Validate dashboard artifacts and the snapshot declared by the HTML."""
    manifest_path = dist / "data-app-build.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    kind = manifest.get("kind")
    if manifest.get("version") != 1 or kind not in {"separate-data-v1", "inline-data-v1"}:
        raise ValueError("Expected a validated dashboard build.")
    html_metadata = manifest.get("html", {})
    snapshot_metadata = manifest.get("snapshot", {})
    if html_metadata.get("path") != "index.html":
        raise ValueError("Dashboard HTML path must be index.html.")
    snapshot_path = snapshot_metadata.get("path", "")
    match = SNAPSHOT.fullmatch(snapshot_path) if isinstance(snapshot_path, str) else None
    if not match or match.group(1) != snapshot_metadata.get("sha256"):
        raise ValueError("Dashboard snapshot path must contain its exact SHA256.")
    if manifest.get("sourceSnapshotSha256") != snapshot_metadata.get("sha256"):
        raise ValueError("Dashboard source and published snapshot hashes disagree.")
    html = checked_bytes(dist / "index.html", html_metadata)
    snapshot = checked_bytes(dist / snapshot_path, snapshot_metadata)
    metadata_parser = SnapshotMetadata()
    metadata_parser.feed(html.decode("utf-8"))
    if kind == "separate-data-v1":
        if metadata_parser.paths != [snapshot_path]:
            raise ValueError("Dashboard HTML must reference exactly its validated snapshot.")
    elif metadata_parser.hashes != [snapshot_metadata["sha256"]] or metadata_parser.paths:
        raise ValueError("Inline dashboard HTML must declare exactly its validated snapshot SHA256.")
    payload = json.loads(snapshot)
    if not isinstance(payload, dict) or not isinstance(payload.get("queries"), dict):
        raise ValueError("Dashboard snapshot has no reviewed query data.")
    return snapshot_path


def publication_files(project_root: Path) -> dict[str, Path]:
    """Use a fixed publication allowlist, never a repository-wide copy."""
    dist = project_root / "dashboard/dist"
    snapshot_path = validate_dashboard(dist)

    files = {
        "index.html": project_root / "site/index.html",
        "dashboard/index.html": dist / "index.html",
        "dashboard/data-app-build.json": dist / "data-app-build.json",
        f"dashboard/{snapshot_path}": dist / snapshot_path,
        "reports/reading.html": project_root / "outputs/notebook.html",
        "reports/audiobooks.html": project_root / "outputs/audiobook_notebook.html",
        "assets/coverage_map.png": project_root / "outputs/coverage_map.png",
        "notebooks/01_reading_and_listening_analysis.ipynb": (
            project_root / "notebooks/01_reading_and_listening_analysis.ipynb"
        ),
        "notebooks/02_audiobook_market_check.ipynb": (
            project_root / "notebooks/02_audiobook_market_check.ipynb"
        ),
        "sources/register.json": project_root / "data/source_register.json",
        "THIRD_PARTY_NOTICES.txt": project_root / "THIRD_PARTY_NOTICES.txt",
        "dashboard/THIRD_PARTY_NOTICES.txt": project_root / "THIRD_PARTY_NOTICES.txt",
    }
    for source in files.values():
        if not source.is_file() or source.is_symlink() or not source.resolve().is_relative_to(project_root):
            raise ValueError(f"Missing or linked publication artifact: {source.name}")
    return files


def validate_output(project_root: Path, output: Path):
    """Allow replacement of this builder's own output, without deleting other files."""
    if output == project_root or project_root.is_relative_to(output):
        raise ValueError("The site output cannot contain the project itself.")
    if output.is_relative_to(project_root) and output.relative_to(project_root).parts[0].startswith("."):
        raise ValueError("Choose a site output outside hidden project directories.")
    protected = (
        "dashboard", "data", "site",
        "src", "tests", "scripts", "notebooks", "outputs",
    )
    for name in protected:
        if output.is_relative_to(project_root / name):
            raise ValueError("Choose a site output outside the project source directories.")
    if not output.exists():
        return
    if not output.is_dir() or output.is_symlink():
        raise ValueError("The site output must be a normal directory.")
    if not any(output.iterdir()):
        return
    receipt_path = output / RECEIPT
    if not receipt_path.is_file() or receipt_path.is_symlink():
        raise ValueError("Refusing to replace a non-empty directory without a site build receipt.")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("kind") != KIND or not isinstance(receipt.get("files"), dict):
        raise ValueError("The existing site build receipt is invalid.")
    expected = set(receipt["files"]) | {RECEIPT}
    actual = {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()}
    expected_directories = {
        parent.as_posix() for name in expected for parent in Path(name).parents if parent != Path(".")
    }
    actual_directories = {
        path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_dir()
    }
    if (
        actual != expected or actual_directories != expected_directories
        or any(path.is_symlink() for path in output.rglob("*"))
    ):
        raise ValueError("Existing site output contains unrelated files; use a new output directory.")


def build_site(project_root: Path = ROOT, output: Path | None = None) -> dict:
    project_root = project_root.resolve()
    output = (output or project_root / "work/site").absolute()
    if output.is_symlink():
        raise ValueError("The site output cannot be a symbolic link.")
    output = output.resolve()
    files = publication_files(project_root)
    validate_output(project_root, output)
    receipt = {"kind": KIND, "files": {}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".atlas-site-", dir=output.parent) as temporary:
        staging = Path(temporary) / "site"
        staging.mkdir()
        for destination, source in files.items():
            target = staging / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            data = target.read_bytes()
            receipt["files"][destination] = {
                "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)
            }
        validate_dashboard(staging / "dashboard")
        (staging / RECEIPT).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        if output.exists():
            previous = Path(temporary) / "previous"
            output.rename(previous)
            try:
                staging.rename(output)
            except OSError:
                previous.rename(output)
                raise
        else:
            staging.rename(output)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, help="Static site folder; defaults to work/site.")
    args = parser.parse_args()
    receipt = build_site(args.project_root, args.output)
    print(f"Packaged {len(receipt['files'])} reviewed artifacts for the static site.")


if __name__ == "__main__":
    main()
