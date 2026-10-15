"""Prepare validated public evidence or open the dashboard in a browser."""

from __future__ import annotations

import argparse
import functools
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import webbrowser

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "work/matplotlib"))


def build_dashboard():
    """Compile dashboard source with its installed Node dependencies."""
    npm = shutil.which(os.environ.get("DATA_APP_NPM", "npm"))
    if not npm:
        raise SystemExit(
            "Install Node.js 24 or later to rebuild the dashboard. "
            "The committed dashboard can still be served with python main.py serve."
        )
    dashboard = ROOT / "dashboard"
    if not (dashboard / "node_modules/vite/package.json").is_file():
        raise SystemExit("Install dashboard dependencies first: cd dashboard && npm ci")
    snapshot = ROOT / "dashboard/src/data.json"
    payload = json.loads(snapshot.read_text())
    payload["buildStatus"] = "complete"
    snapshot.write_text(json.dumps(payload, indent=2) + "\n")
    subprocess.run(
        [npm, "run", "build"], cwd=dashboard, check=True
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        nargs="?",
        default="serve",
        choices=["serve", "prepare", "audit", "build", "validate", "refresh"],
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Explicitly refresh Eurostat and map inputs when preparing evidence",
    )
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument(
        "--open-browser", action="store_true", help="Open the dashboard in the default browser"
    )
    parser.add_argument(
        "--notebooks", action="store_true", help="Re-execute both shared-data notebooks after a refresh"
    )
    args = parser.parse_args()
    if args.command == "serve":
        folder = ROOT / "dashboard/dist"
        if not (folder / "index.html").exists():
            raise SystemExit("Dashboard build is missing. Run python main.py build first.")
        handler = functools.partial(SimpleHTTPRequestHandler, directory=str(folder))
        try:
            server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
        except OSError as exc:
            raise SystemExit(
                f"Could not start the dashboard: {exc}. Try another port with --port 4174."
            ) from exc
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"Global Reading Atlas: {url}", flush=True)
        if args.open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return
    if args.command == "refresh":
        from src.updates import check_sources

        print(json.dumps(check_sources(), indent=2))
    if args.command in {"prepare", "audit", "refresh"}:
        from src.audit import main as audit

        audit(["--refresh"] if args.refresh else [])
    if args.command in {"prepare", "build", "refresh"}:
        from src.analysis import build_analysis

        print(json.dumps(build_analysis(), indent=2))
    if args.command in {"build", "refresh"}:
        build_dashboard()
    if args.command in {"prepare", "build", "validate", "refresh"}:
        from src.validation import validate_cached_evidence

        result = validate_cached_evidence()
        (ROOT / "outputs/validation.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    if args.notebooks:
        import sys

        for script in ["build_notebook.py", "build_audiobook_notebook.py"]:
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "notebooks" / script),
                    "--project-root",
                    str(ROOT),
                    "--output-root",
                    str(ROOT),
                ],
                check=True,
            )


if __name__ == "__main__":
    main()
