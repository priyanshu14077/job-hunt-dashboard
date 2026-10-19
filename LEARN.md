# Learning data analytics with this project

Each lesson uses one file in this repo. Read the code, then run the snippet in a
REPL (`uv run python`) and do the exercise. Every number below comes from your
sheet as of 2026-10-19.

The pipeline follows the standard **extract → transform → analyse → visualise** order:

```
Google Sheet ─► load.py ─► clean.py ─► (pandas analysis) ─► charts.py ─► app.py
 13 tabs        631 rows    408 jobs                         plotly       Streamlit
```

Start every REPL session with:

```python
import numpy as np, pandas as pd
from jobdash.load import load_raw
from jobdash.clean import build
raw = load_raw()
jobs, stack = build(raw)
```

---

## Lesson 1: Extract. Many tabs, one schema (`load.py`)

**The problem.** Thirteen tabs describe the same thing with different headers:
"Role", "Job Title", "Hub / Location", "Country / Tech Hub". You can't stack them
until they share column names.

**Concepts**
- **Schema mapping.** `HEADER_RULES` maps every raw header onto a canonical name.
  Rules are ordered, so the specific "Role Category & Level" matches before the
  generic "role" does.
- **`pd.concat`** stacks DataFrames vertically. A tab that lacks a column gets
  `NaN` there. Missing data is normal, not an error.
- **The display value is not the data.** pandas reads "Apply Now" from a link cell.
  The URL lives inside the `=HYPERLINK("…")` formula, which `openpyxl` can read.
- **Validate the shape you got.** 32 rows had one cell missing, so every value
  after it slid one column left (a tech stack sitting in the compensation column).
  `repair_shifted_rows` uses "type sniffers" (small regexes that check whether a
  cell looks like money, a date, or a team size) to decide where the gap was.

```python
raw.shape                                   # (631, 16)
raw["source_sheet"].value_counts()
raw.notna().mean().sort_values()            # completeness of each column
raw[raw.was_repaired][["company", "compensation"]].head()
```

**Exercise.** Add a 14th tab with a new header, such as "Salary Band". Run `load_raw()`
and read the `KeyError`. Then add a rule to `HEADER_RULES`.

---

## Lesson 2: Transform. Text into numbers (`clean.py`)

**Concepts**
- **Regex extraction.** `Series.str.extract(pattern)` returns the captured groups
  as columns. It's the main tool for messy text.
- **Parsing money.** `"£65k - £95k GBP / ~€75k EUR + Equity"`: keep the first
  range, find the currency, read both numbers, and handle `k`. Indian grouping
  (`20,00,000`) also works, because we drop the commas and never interpret them.
- **Normalise before comparing.** Pay arrives in 11 currencies, some per month.
  `pay × FX rate × (12 if monthly)` is **vectorised** NumPy maths: one
  expression for the whole column, no loop.
- **`np.select`** is a vectorised if/elif/else. See `remote_type` and `seniority`.
  The first true condition wins, so the order of conditions is the logic.
- **Typed categories.** `pd.Categorical(..., ordered=True)` makes
  "Junior < Mid < Senior" sort correctly and keeps chart order stable.
- **Record uncertainty.** A date is stored with its `posted_precision`
  (`day` / `month` / `unknown`). Only 63 jobs have an exact day. Plotting the other
  288 on "Oct 1" would invent a spike that never happened.

```python
from jobdash.clean import parse_compensation
parse_compensation("kr.55k - kr.75k SEK/mo (~€65k - €90k/yr)")
jobs.currency.value_counts()
jobs[["compensation", "pay_mid_eur"]].sample(5)
jobs.posted_precision.value_counts()
```

**Exercise.** `seniority` labels 320 of 408 jobs as "Mid" because most titles
just say "Software Engineer". Write a rule that also uses the `fit_notes` text
(e.g. "1.5 yrs", "early-career") and see how the counts move.

---

## Lesson 3: De-duplication and tidy data

**Concepts**
- **A join key.** `job_key` lowercases the text, drops "(…)" and punctuation, and
  combines company + title. 631 rows collapse to **408 distinct jobs**, so 223 were
  repeats across tabs.
- **`groupby().first()` coalesces.** It takes the first *non-null* value per
  column, so if one tab knows the team size and another knows the date, the merged
  row keeps both.
- **`transform`** returns a result aligned to the original rows.
  `listed_in_tabs` counts how many tabs each job appeared in, which is a free
  signal of how strong a match it is.
- **Tidy (long) data.** A cell like "Python, Go, React" is three facts in one
  cell. `.explode("stack")` gives one row per (job, technology), and then
  "most requested tech" is just `stack.tech.value_counts()`.

```python
jobs.listed_in_tabs.value_counts()
stack.head()
stack.groupby("region_group")["tech"].value_counts().groupby(level=0).head(3)
```

**Exercise.** Build `pd.crosstab(stack.tech, stack.seniority)` for the top 10
technologies. Do junior roles ask for a different stack?

---

## Lesson 4: Analysis. Statistics that don't lie

**Concepts**
- **Median over mean for pay.** Pay is right-skewed (a few $250k roles). The mean
  is €84k and the median is €80k. The median describes the typical job.
- **Outliers with Tukey's rule.** Anything outside `[Q1 − 1.5·IQR, Q3 + 1.5·IQR]`
  gets flagged (`flag_outliers`, built on `np.nanpercentile`). Five jobs are flagged:
  - **Real but extreme:** PostHog and LiveKit ($135–300k).
  - **Real but low:** an Indian salary in INR.
  - **Data errors:** `¥8,00,000` for LayerX is almost certainly `¥8,000,000`.
  Flagging is not deleting. Look at each one and decide.
- **Normalise counts into shares.** Europe has the most jobs, so raw counts per
  region just repeat that. The heatmap shows *% of that region's jobs*.
- **Small-n honesty.** A group with one job has a "median" but no distribution.
  The charts drop groups with fewer than 5 jobs and show `n=` on each label.
- **A metric you define yourself.** `skill_match_pct` is the share of a role's
  stack that appears in `MY_SKILLS`. It's crude (all tags weigh the same), and you
  should know that when you use it.

```python
jobs.groupby("region_group")["pay_mid_eur"].agg(n="size", median="median")
jobs.loc[jobs.pay_outlier, ["company", "compensation", "pay_mid_eur"]]
np.corrcoef(jobs.skill_match_pct.fillna(0), jobs.pay_mid_eur)[0, 1]   # ≈ -0.19
```

That last number is a finding. Roles that match your stack better pay slightly
*less* (r ≈ −0.19, which is weak). One likely reason: higher-paid roles list
infrastructure (Kubernetes, distributed systems) that is not in `MY_SKILLS`.
Correlation doesn't prove that, so check it in the scatter on the Pay tab.

**Exercise.** Weight `skill_match_pct` so the first tag listed (usually the main
language) counts twice. Does the order on the Job board change?

---

## Lesson 5: Design. Choosing and drawing charts (`charts.py`, `app.py`)

**Choose the form from the question**

| Question | Form used here |
|---|---|
| A few headline numbers | KPI row (`st.metric`), not a chart |
| Which is biggest? | Horizontal bars, **sorted** by value |
| How is it spread? | Box plot + the individual points |
| Two measures together? | Scatter (match × pay) |
| Two categories crossed? | Heatmap with a single-hue ramp |
| Change over time | Bars by day, only where the day is known |

**Rules applied**
- **Colour has a job.** One series gets one colour and no legend. The tech chart
  uses colour to answer one question (in your skills = blue, gap = grey). Magnitude
  uses one hue from light to dark, never a rainbow.
- **Colour follows the entity.** Seniority colours are pinned with
  `category_orders`, so filtering never repaints "Senior" a different colour.
- **One y-axis per chart.** If two measures have different scales, draw two charts.
- **Quiet ink.** Faint grid, no axis titles where the chart title already says it,
  direct value labels on bars instead of a tick-reading exercise.
- **Filters above, KPIs next, detail last.** People read the dashboard top to
  bottom, from general to specific: overview → why → raw rows.
- **Show the data's weaknesses.** The Data quality tab is part of the dashboard.
  It tells the reader how far to trust everything else.

- **Plan for thin data.** Filters can leave 0 or 1 jobs. Every chart function
  returns `None` when it can't draw something honest, and `show_chart` prints a
  note instead. `tests/test_app.py` runs the real app through dozens of filter
  combinations to catch crashes before a user does.

**Exercise.** Add a "Pay by funding stage" box plot to the Insights tab with
`show_chart(charts.pay_by_group(view, "stage"), "pay-stage")`. The key must be unique.

---

## Where to go next

1. **Persist the cleaned data.** `jobs.to_parquet("data/processed/jobs.parquet")`
   (install `pyarrow`). Load that file in the app instead of rebuilding it.
2. **Track applications.** Add a `status` column (applied / interview / rejected)
   in your own sheet and build a funnel chart.
3. **Test the next parser first.** `tests/test_clean.py` shows the pattern: one
   real messy string in, one expected value out.
