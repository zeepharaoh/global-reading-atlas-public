# Open and share Global Reading Atlas

## Explore without installing anything

Open **[Global Reading Atlas](https://zeepharaoh.github.io/global-reading-atlas-public/)** in a browser. The start page links to the interactive dashboard and two readable analysis reports. No account, editor or installation is needed.

Start with **Audiobooks** for listening evidence, observed history, genres and listening moments. Use **Industry** for the company landscape and published market series. **Formats**, **Genres**, **Reading** and **Coverage** show the other evidence and its gaps. The source inspector retains the original source and measurement notes.

The evidence is public. This independent project contains no internal Storytel business data and is not an official Storytel publication. Coverage is incomplete. Survey populations, questions and periods differ; the dashboard does not establish a worldwide country ranking or a verified next-country investment winner.

## Download the project

Clone the [public repository](https://github.com/zeepharaoh/global-reading-atlas-public) with Git, use your editor's clone command, or choose **Code → Download ZIP** on GitHub and extract the whole archive.

```bash
git clone https://github.com/zeepharaoh/global-reading-atlas-public.git
cd global-reading-atlas-public
```

Keep the project folder together, including `data/`, `notebooks/` and `dashboard/dist/`. You can use a terminal or any Python editor; no particular IDE is required.

## Run the dashboard locally

From the extracted or cloned project folder, use Python 3.12 or newer:

```bash
python3 main.py serve --open-browser
```

On Windows use `py -3` in place of `python3`. No package installation is needed to view the committed build. The dashboard starts on `http://localhost:4173/`; keep the terminal open while exploring and press Ctrl+C to stop it. If the port is busy, add `--port 4174` and use the address shown in the terminal.

The local address points to each person's own computer. Use the public browser link when sending the dashboard to someone else.

## Run the actual notebooks

Existing results can be viewed in the browser reports or GitHub notebook previews without setting up Python. To run or edit the notebooks, install the analysis dependencies in a project environment.

macOS / Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install ".[analysis]" jupyterlab
.venv/bin/python -m jupyterlab
```

Windows:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install ".[analysis]" jupyterlab
.venv\Scripts\python.exe -m jupyterlab
```

These commands start JupyterLab in your browser using the project environment. Open either notebook from its file browser, select that environment's Python kernel and run all cells in order:

- `notebooks/02_audiobook_market_check.ipynb`: audiobook evidence, genres, coverage and separate Storytel case studies.
- `notebooks/01_reading_and_listening_analysis.ipynb`: reading participation, demographics and source comparability.

The notebooks use cached reviewed public data. Opening or running them does not require Storytel access. Their Python cells are editable, and the reports retain source definitions and measurement limits.

### Use VS Code or another notebook editor

In VS Code, install the Microsoft Python and Jupyter extensions, open the project folder and either notebook, then choose the project `.venv` through **Select Kernel**. Run all cells from the notebook toolbar. The [official VS Code notebook guide](https://code.visualstudio.com/docs/datascience/jupyter-notebooks) explains the editor controls.

Other Jupyter-compatible editors work with the same `.ipynb` files and environment. Start from the project folder so the notebooks can find `data/`.

### Optional: use PyCharm

Open the project folder and select the `.venv` interpreter. The saved **Dashboard** run configuration starts the dashboard; open either notebook and select the same `.venv` kernel to run its cells. If your editor does not provide notebook controls, use JupyterLab or the notebook-builder commands in the [maintainer guide](MAINTAINING.md).

## Get updates and contribute

Download a fresh ZIP or clone into a new folder to get the latest version. Save your own notebooks and changes separately. The public repository is shared as one release snapshot, so an older clone may need to be replaced rather than updated with Git pull. The browser edition receives the latest successfully validated deployment.

Open a GitHub issue for a missing country, company, source or reproducible problem. For data suggestions, include the official source URL, observation year, table/page, metric, unit, geography, population and recall period. Published and reviewed evidence is added through the validation pipeline; unavailable years stay missing.

Viewing the dashboard needs only Python. Running the notebooks needs the analysis environment. Changing and rebuilding the interactive app has additional Node.js requirements, covered in the [maintainer guide](MAINTAINING.md).

## Suggested message to colleagues

> I've put together Global Reading Atlas, a public-source project on paper books, ebooks and audiobooks, including genres, market evidence and company coverage. You can explore the dashboard and read both analyses here: https://zeepharaoh.github.io/global-reading-atlas-public/
>
> No setup is needed for the browser version. The Python project and two real notebooks are on GitHub: https://github.com/zeepharaoh/global-reading-atlas-public. You can rerun or extend the analysis in JupyterLab, VS Code or your preferred Python editor; the README has the setup steps.
>
> The source notes matter: survey bases differ and coverage is incomplete. The Storytel entry and existing-market growth sections are separate case studies, using public evidence only.
