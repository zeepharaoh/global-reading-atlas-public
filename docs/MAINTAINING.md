# Maintaining the project

Use Python 3.12 or newer. Create the project environment described in the [README](../README.md#work-with-the-notebooks), then install the development and analysis dependencies in it. The commands below use `python` from that environment; activate it first or use `.venv/bin/python` on macOS/Linux and `.venv\Scripts\python.exe` on Windows.

```bash
python -m pip install ".[analysis,dev]"
python main.py prepare
python main.py validate
python -m ruff check main.py src tests scripts
python -m pytest -q
python notebooks/build_notebook.py --project-root . --output-root .
python notebooks/build_audiobook_notebook.py --project-root . --output-root .
```

Preparation uses cached reviewed data. The notebook builders execute every cell and save the `.ipynb`, HTML reports and figures. `requirements-lock.txt` records the reference environment versions; it is not a portable system configuration.

## Evidence refresh

`python main.py audit` checks cached evidence. `python main.py prepare --refresh` refreshes the cached Eurostat 2022 baseline and map geometry before rebuilding analytical tables. Changed survey PDFs and company releases require review before new extracts are accepted.

Keep source URL, exact table/page, unit, geography, population, recall period and report vintage attached to each observation. Review changes against the original evidence. Failed source checks must retain the last validated observations. A successful URL check does not validate a new data point.

`python main.py refresh --notebooks` checks public releases, refreshes supported Eurostat and Norwegian paper/ebook API observations, rebuilds the dashboard and executes both notebooks. It requires network access, the Python analysis environment and the Node.js setup below. The browser edition serves reviewed results; it does not run this refresh command for visitors.

## Build the interactive dashboard

Use **Node.js 24 LTS with npm**. Install the dashboard's locked JavaScript dependencies once, and again when its lockfile changes:

```bash
cd dashboard
npm ci
npm audit --audit-level=low
npm run build
npm test
```

For changes to dashboard views only, rerun `npm run build` from `dashboard/`. To rebuild analytical tables and the dashboard together, return to the project root and use the Python environment:

```bash
python main.py build
```

This command expects npm on your PATH and the dashboard dependencies already installed. Dashboard builds use the source and build configuration included in the repository. Run `npm test` inside `dashboard/` after building to check chart interactions, exports, view links and evidence integrity. Viewing the committed dashboard requires no Node.js setup.

Keep the bundled application runtime and integrity records intact. Change authored views in `dashboard/src/content/`; rebuild reviewed data with `python main.py prepare` before rebuilding the app. Inspect affected charts, filters and source details after building. Refresh third-party notices when dependencies change.

## Browser edition

The static package includes an explicit list of reviewed artifacts. It preserves the compiled dashboard and snapshot bytes and verifies their hashes before publishing. It also includes both HTML reports, downloadable notebooks, source register, coverage image and dependency notices. Notebook reports contain embedded figures and tables, with no browser scripts or automatic external assets. The report exporter rejects active content before replacing an existing report.

```bash
python scripts/build_site.py --output work/site
python -m http.server 4180 --bind localhost --directory work/site
```

Preview `http://localhost:4180/`. The builder refuses to overwrite source folders or unrelated files.

GitHub Pages uses GitHub Actions as its publishing source. The workflow uses Node.js 24, installs locked dashboard dependencies, builds the app from source and runs the project checks before deploying from `main`. Pull requests validate without deploying. After reviewing new evidence, commit updated data, notebook outputs and the dashboard build together.
