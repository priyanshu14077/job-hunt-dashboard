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

## How it works

### The pipeline

Data moves one way, through four stages. Each stage is one module, so you can
run and test each stage separately.

```mermaid
flowchart LR
    sheet[("Google Sheet<br/>13 tabs")] -->|"export as .xlsx"| load
    subgraph extract ["1 · Extract — load.py"]
        load["Map headers to one schema<br/>Read =HYPERLINK() URLs<br/>Repair shifted rows"]
    end
    subgraph transform ["2 · Transform — clean.py"]
        clean["Pay → EUR / yr<br/>Dates, region, remote type<br/>Stage, seniority, tech tags"]
        dedupe["Merge duplicates<br/>631 rows → 408 jobs"]
        clean --> dedupe
    end
    subgraph slice ["3 · Slice — filters.py"]
        filt["Filters → one boolean mask<br/>Sort"]
    end
    subgraph show ["4 · Visualise — app.py"]
        ui["Job board · Insights · Data quality"]
    end
    load -->|"raw rows"| clean
    dedupe -->|"jobs + stack_long"| filt
    filt -->|"view"| ui
    config[/"config.py<br/>FX rates · MY_SKILLS · aliases"/] -.-> clean
    charts["charts.py<br/>board.py"] -.-> ui
```

### Fixing a shifted row

In 32 rows one cell was missing, so every value after it slid one column left.
`repair_shifted_rows` tries putting the gap back at each position, from the
compensation column leftwards. It scores each attempt with type sniffers and
keeps the best one.

```mermaid
flowchart TD
    row["Row where 'compensation'<br/>does not look like money"] --> try["Re-insert the missing cell at position j"]
    try --> score["Score: +1 for each cell that passes its sniffer<br/>−1 for each that fails<br/>money · date · team size · remote · Apply"]
    score --> more{"More positions<br/>to try?"}
    more -->|yes| try
    more -->|no| keep["Keep the best-scoring row<br/>ties → smallest shift"]
```

### Turning one messy pay cell into numbers

```mermaid
flowchart LR
    a["'£65k - £95k GBP / ~€75k EUR + Equity'"] -->|"keep first range"| b["'£65k - £95k GBP'"]
    b -->|"find currency"| c["GBP"]
    b -->|"read numbers, apply k"| d["65,000 · 95,000"]
    c & d -->|"× FX rate × 12 if monthly"| e["€74,750 – €109,250 / yr"]
    e -->|"Tukey's rule"| f{"Outlier?"}
```

### What happens when you change a filter

Streamlit re-runs `app.py` from top to bottom on every interaction. The slow
part (download, parse, clean) is cached, so a re-run only filters and draws.

```mermaid
sequenceDiagram
    actor You
    participant App as app.py
    participant Cache as st.cache_data
    participant F as filters.py
    participant C as charts.py
    You->>App: change a filter
    App->>Cache: get_data(file modified time)
    Cache-->>App: raw, jobs, stack_long (cached)
    App->>F: filter_jobs(jobs, Criteria)
    F-->>App: view (filtered + sorted)
    App->>C: one call per chart
    C-->>App: figure, or None if too few jobs
    App-->>You: KPIs, job cards, charts
    Note over App,C: None → a short note instead of a chart.<br/>Every chart has a fixed key, so two empty charts never collide.
```

Clicking **Refresh from Google Sheet** downloads the file again. Its modified
time changes, which is the cache key, so the next run rebuilds everything.

### Tidy data: one row per (job, technology)

`clean.build` returns two tables. `jobs` has one row per job. `stack_long` is
the same data "exploded" to one row per technology, so counting technologies
takes one line.

```mermaid
erDiagram
    JOBS ||--o{ STACK_LONG : "explode('stack')"
    JOBS {
        string job_key PK
        string company
        string title
        string region_group
        float pay_mid_eur
        float skill_match_pct
        list stack
    }
    STACK_LONG {
        string job_key FK
        string tech
        string region_group
        float pay_mid_eur
    }
```

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
