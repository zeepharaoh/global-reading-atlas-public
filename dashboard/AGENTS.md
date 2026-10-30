# Project conventions

Paths and commands below refer to the repository root.

## Evidence and analysis

- Retain source IDs, URLs, page/table locators, observation years and source-check dates.
- Keep survey population, denominator, recall period and format definition explicit.
- Preserve nulls and unreported values. Do not fill missing years or country estimates.
- Compare compatible measures only. Annual participation, reader subsets, daily reach and listener preferences are separate measures.
- Do not sum overlapping formats or multiple-response genre percentages.
- Keep new-country entry screening separate from existing-market growth research, and distinguish brand presence from Group availability.
- Reconcile consequential calculations with the reviewed source rows. Descriptive survey results do not establish causal effects or commercial returns.

## Structure

Python processing and validation live in `src/`; reviewed observations live in `data/curated/`. Dashboard content lives in `dashboard/src/content/`, with reviewed evidence in `dashboard/src/data.json`. Preserve stable application, tab and component identifiers when updating content or data.

Keep third-party runtime files, integrity records and legal notices intact. Use the existing public component APIs for dashboard content. Source views, filters and exports must describe the same displayed population.

## Validation and builds

Run preparation, evidence validation, relevant tests and both notebook builders after data changes. Inspect charts, labels, filters and source records after dashboard changes.

Use Node.js 24 LTS. Install the locked dashboard dependencies with `npm ci` inside `dashboard/`, then build with `npm run build`. From the project root, `python main.py build` also prepares the analysis and builds the dashboard. Runtime integrity checks must pass. Serve with `python main.py serve`.

Refresh with `python main.py refresh --notebooks`. Preserve the last reviewed data on source failures and require extraction review for changed manual sources.
