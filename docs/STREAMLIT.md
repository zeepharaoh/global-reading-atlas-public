# Streamlit companion

**[Open the public Streamlit dashboard](https://globalreadingatlas.streamlit.app/)**. No installation is needed to view it.

The Streamlit app uses the same reviewed snapshot as the browser dashboard and notebooks. It opens on Audiobooks and includes Industry, Reading, Formats, Genres, Coverage and Reports views.

## Run locally

Use Python 3.12 from the project folder.

macOS or Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run streamlit_app.py
```

Windows:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

Open `http://localhost:8501`. Keep the terminal running and press Ctrl+C to stop. If the port is busy, append `--server.port 8502` and open `http://localhost:8502`.

Any Python editor works. A Streamlit run configuration is also included for PyCharm.

## Explore the evidence

Choose a view in the sidebar and set the observation years. Audiobooks starts with Sweden's daily reach observations. Choose another country to inspect its own survey base. The app keeps national participation, daily reach and reader subsets separate.

Industry includes 29 country profiles with published monetary evidence. Choose Country, then Revenue measure. Publisher receipts, retail turnover, operating revenue and sales estimates keep their own units and scope. Some countries have only a historical 2022 observation. Separate audiobook revenue is available for the United States, United Kingdom, Sweden and Spain. The company list has a separate reporting scope and retains parent and brand overlap. See the [industry review](INDUSTRY_REVIEW_20261025.md) for sources and exclusions. Reading shows the comparable Eurostat 2022 measure, which includes audiobooks. Formats and Genres preserve overlapping responses and missing observations. Coverage includes an interactive world map of source review status. Hover over a coloured country for evidence details and use Audit status to filter the map, counts and table together. Map boundaries are bundled locally, so no map service or external tiles are needed. Small territories remain in the full country table even when the map scale omits them.

Genres puts all 14 countries with reviewed genre evidence into one country list. Select a country, then its survey source, genre question, format and observation year. Book and reading surveys remain separate from the 2026 audiobook listener study commissioned by Storytel. Listener study results describe audiobook listeners rather than national participation; only the five published genres per country are available. Listening moments remain in the Audiobooks view.

Each measurement view shows its latest available observation and the latest source check for the selected country and measure. When the selected ending year has no reviewed observation, the app says so instead of filling the gap. A source checked in 2026 can still contain only 2025 observations.

Each measurement has a source data panel. It contains the exact displayed rows, definitions, original source links and a CSV download. Reset filters restores the defaults for the current view.

Reports opens the saved audiobook and reading analyses inside Streamlit. Report previews and HTML downloads show the analysis, tables and charts without code cells. Download the original .ipynb notebook to read or run the full code. The reports use the full reviewed dataset, so dashboard filters do not change them. The sidebar source code link opens the public GitHub repository.

The dashboard presents audience, genre and industry evidence. Country entry and growth conclusions are developed separately from the dashboard.

## Share a hosted app

Share [globalreadingatlas.streamlit.app](https://globalreadingatlas.streamlit.app/) with colleagues to open the Streamlit app. Streamlit Community Cloud hosts it from the public repository. GitHub Pages continues to host the separate browser dashboard and notebook reports.

For Streamlit Community Cloud, select the public repository `zeepharaoh/global-reading-atlas-public`, branch `main`, and main file `streamlit_app.py`. Choose Python 3.12 in the deployment settings. The root `requirements.txt` supplies the app dependencies. No secrets or Storytel access are required.

The local configuration binds to `localhost`. A hosting service must supply its own server binding and public browser address through its deployment settings or command line. Keep CORS and XSRF protection enabled. Follow the hosting service's networking instructions before making an app public.

The public Streamlit address works in a browser without a local Python process. The local address works only on the computer running the app. Streamlit and GitHub Pages have separate public addresses.

See the official [Community Cloud deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app) and [configuration reference](https://docs.streamlit.io/develop/api-reference/configuration/config.toml).

## Refresh and validate

The app reads `data/processed/dashboard_snapshot.json`. It makes no source API calls and cannot change the reviewed observations. After an evidence refresh, the next interaction loads the updated snapshot. Source check dates remain separate from observation years.

Install the analysis, development and Streamlit extras to run the complete project checks:

```bash
python -m pip install ".[analysis,dev,streamlit]"
python -m ruff check main.py streamlit_app.py src tests scripts
python -m pytest -q
```

`requirements-streamlit.in` records the app's direct dependencies. `requirements.txt` pins the complete app environment, including platform markers. To update it, review the new versions and run:

```bash
uv pip compile --universal --python-version 3.12 --no-header --no-annotate requirements-streamlit.in --output-file requirements.txt
```

Run the app tests and check dependency advisories after updating. Usage statistics and arbitrary static file serving are disabled in `.streamlit/config.toml`. Keep private credentials out of the project; local Streamlit secrets files are ignored by Git.
