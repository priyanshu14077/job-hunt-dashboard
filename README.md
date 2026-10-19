# Job hunt dashboard

A Streamlit dashboard built from the job-postings Google Sheet (13 tabs) using
pandas, NumPy and Plotly. For the step-by-step lessons, see [LEARN.md](LEARN.md).

## Run

```bash
uv sync
uv run streamlit run app.py      # opens http://localhost:8501
uv run pytest                    # 50 tests: parsers, filters, charts, full-app sweep
```

The app downloads the sheet on first run (it must be shared as "anyone with the
link"). The **Refresh from Google Sheet** button downloads it again.

## Layout

| File | Role |
|---|---|
| `src/jobdash/load.py` | Extract: download, map headers to one schema, read link URLs, repair shifted rows |
| `src/jobdash/clean.py` | Transform: pay → EUR, dates, region, remote type, company stage, seniority, tech tags, de-duplication |
| `src/jobdash/config.py` | **Edit this:** FX rates, `MY_SKILLS`, tech-name aliases |
| `src/jobdash/filters.py` | Slice: filter choices → one boolean mask, plus sorting |
| `src/jobdash/board.py` | Text for each job card (Markdown-safe) |
| `src/jobdash/charts.py` | One Plotly function per chart; returns None when data is too thin |
| `app.py` | Streamlit layout: filters, KPIs, Job board / Insights / Data quality tabs |
