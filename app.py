"""Job-hunt dashboard. Run with:  uv run streamlit run app.py"""

import math

import pandas as pd
import streamlit as st

from jobdash import board, charts
from jobdash.clean import build
from jobdash.config import MY_SKILLS
from jobdash.filters import SORTS, Criteria, filter_jobs
from jobdash.load import RAW_PATH, download, load_raw

st.set_page_config(page_title="Job Hunt Dashboard", page_icon="📊", layout="wide")

PAGE_SIZE = 20


@st.cache_data
def get_data(_mtime: float):
    # The file's modified time is the cache key: a fresh download busts the cache.
    raw = load_raw()
    jobs, stack_long = build(raw)
    return raw, jobs, stack_long


def show_chart(fig, key: str, empty: str = "Not enough jobs in this selection to draw this chart."):
    """Every chart gets a fixed key: Streamlit otherwise derives an ID from the
    figure itself, and two identical figures (e.g. both empty) collide."""
    if fig is None:
        st.info(empty)
    else:
        st.plotly_chart(fig, width="stretch", key=key)


def options(series: pd.Series) -> list[str]:
    return sorted(series.dropna().astype(str).unique())


try:
    if not RAW_PATH.exists():
        download()
    raw, jobs, stack_long = get_data(RAW_PATH.stat().st_mtime)
except Exception as exc:  # network down, sheet unshared, file corrupt
    st.error(f"Couldn't load the job sheet: {exc}")
    st.caption("Check that the Google Sheet is still shared as 'anyone with the link', "
               "then reload the page.")
    st.stop()

# ------------------------------------------------------------------ header
left, right = st.columns([4, 1], vertical_alignment="bottom")
with left:
    st.title("Job hunt dashboard")
    st.caption(f"{len(raw)} rows across {raw['source_sheet'].nunique()} tabs, merged into "
               f"{len(jobs)} distinct jobs. Pay is converted to EUR per year.")
with right:
    if st.button("Refresh from Google Sheet", width="stretch"):
        try:
            download()
            st.rerun()
        except Exception as exc:
            st.error(f"Refresh failed: {exc}")

# ---------------------------------------------------------------- filters
pay_known = jobs["pay_mid_eur"].dropna()
pay_max_k = int(math.ceil(pay_known.max() / 10_000) * 10) if not pay_known.empty else 100

with st.container(border=True):
    search = st.text_input("Search", placeholder="Company, title, tech, location… e.g. 'python remote'")
    f1, f2, f3, f4 = st.columns(4)
    regions = f1.multiselect("Region", options(jobs["region_group"]))
    countries = f2.multiselect("Country", options(jobs["country"]))
    seniority = f3.multiselect("Seniority", list(jobs["seniority"].cat.categories))
    remote = f4.multiselect("Remote", options(jobs["remote_type"]))
    g1, g2, g3, g4 = st.columns(4)
    stages = g1.multiselect("Funding stage", [s for s in jobs["stage"].cat.categories
                                              if s in set(jobs["stage"].dropna())])
    techs = g2.multiselect("Must use (all of)", options(stack_long["tech"]))
    pay_range = g3.slider("Pay midpoint (€k / yr)", 0, pay_max_k, (0, pay_max_k), step=5)
    min_match = g4.slider("Min skill match (%)", 0, 100, 0, step=10)
    h1, h2, _ = st.columns([1, 1, 2])
    sort = h1.selectbox("Sort by", list(SORTS))
    hide_outliers = h2.toggle("Hide pay outliers", value=False,
                              help="Jobs whose pay is unusually high or low (see Data quality).")

criteria = Criteria(
    search=search, regions=regions, countries=countries, seniority=seniority, remote=remote,
    stages=stages, techs=techs, min_match=min_match, hide_outliers=hide_outliers, sort=sort,
    # Leave pay unfiltered at the full range so jobs without a listed pay stay visible.
    pay_range_k=None if pay_range == (0, pay_max_k) else pay_range,
)
view = filter_jobs(jobs, criteria)
view_stack = stack_long[stack_long["job_key"].isin(view["job_key"])]

# -------------------------------------------------------------- KPI row
def fmt(value, template, missing="–"):
    return missing if pd.isna(value) else template.format(value)


k = st.columns(5)
k[0].metric("Jobs", f"{len(view)} of {len(jobs)}")
k[1].metric("Median pay", fmt(view["pay_mid_eur"].median() / 1000, "€{:,.0f}k"),
            help="Median of each pay range's midpoint, EUR per year")
k[2].metric("Fully remote", fmt((view["remote_type"] == "Fully remote").mean(), "{:.0%}"))
k[3].metric("Median skill match", fmt(view["skill_match_pct"].median(), "{:.0f}%"))
k[4].metric("Junior / entry roles", f"{(view['seniority'] == 'Junior / Entry').sum()}")

if view.empty:
    st.warning("No jobs match these filters. Clear one or two to see results.")
    st.stop()

t_board, t_insights, t_quality = st.tabs(["Job board", "Insights", "Data quality"])

# ------------------------------------------------------------- job board
with t_board:
    b1, b2, b3 = st.columns([2, 1, 1], vertical_alignment="bottom")
    layout = b1.segmented_control("View", ["Cards", "Table"], default="Cards")
    pages = max(1, math.ceil(len(view) / PAGE_SIZE))
    page = b2.number_input(f"Page (of {pages})", min_value=1, max_value=pages, value=1, step=1)
    b3.download_button("Download CSV", view.drop(columns=["stack"]).to_csv(index=False),
                       "jobs_filtered.csv", "text/csv", width="stretch")

    if layout == "Table":
        cols = ["company", "title", "region_group", "country", "remote_type", "seniority",
                "pay_mid_eur", "skill_match_pct", "stage", "headcount", "posted", "apply_url"]
        st.dataframe(
            view[cols], hide_index=True, width="stretch", height=640,
            column_config={
                "pay_mid_eur": st.column_config.NumberColumn("Pay (EUR)", format="€%d"),
                "skill_match_pct": st.column_config.ProgressColumn(
                    "Skill match", format="%d%%", min_value=0, max_value=100),
                "apply_url": st.column_config.LinkColumn("Apply", display_text="Open"),
                "posted": st.column_config.DateColumn("Posted"),
            },
        )
    else:
        start = (int(page) - 1) * PAGE_SIZE
        chunk = view.iloc[start:start + PAGE_SIZE]
        st.caption(f"Showing {start + 1}–{start + len(chunk)} of {len(view)}")
        grid = st.columns(2)
        for i, (_, job) in enumerate(chunk.iterrows()):
            with grid[i % 2].container(border=True):
                head, cta = st.columns([4, 1], vertical_alignment="top")
                head.markdown(f"**{board.md(job['title'])}**  \n{board.md(job['company'])}")
                url = job["apply_url"]
                cta.link_button("Apply", url if board.is_url(url) else "https://example.com",
                                disabled=not board.is_url(url), width="stretch",
                                key=f"apply-{start + i}")
                st.caption(board.meta_line(job))
                p, m = st.columns(2)
                p.markdown(f"**{board.md(board.pay_line(job))}**")
                match = job["skill_match_pct"]
                if pd.notna(match):
                    m.progress(int(match) / 100, text=f"Skill match {match:.0f}%")
                badges = board.tech_badges(job["stack"], MY_SKILLS)
                if badges:
                    st.markdown(badges)
                with st.expander("Why it fits · details"):
                    if board.md(job["fit_notes"]):
                        st.markdown(board.md(job["fit_notes"]))
                    if board.md(job["summary"]):
                        st.markdown(f"**Role:** {board.md(job['summary'])}")
                    st.caption(f"Pay as listed: {board.md(job['compensation'])}")
                    st.caption(f"{board.posted_label(job)} · listed in {job['listed_in_tabs']} "
                               f"tab{'s' if job['listed_in_tabs'] != 1 else ''}")

# -------------------------------------------------------------- insights
with t_insights:
    a, b = st.columns(2)
    with a:
        st.subheader("Jobs by region")
        show_chart(charts.bar_ranked(view["region_group"].value_counts()), "region")
    with b:
        st.subheader("Remote policy")
        show_chart(charts.bar_ranked(view["remote_type"].value_counts()), "remote")

    st.subheader("Pay by region")
    st.caption("Box = middle 50% of jobs, line = median, dots = individual jobs. "
               "Outliers and groups under 5 jobs are left out.")
    show_chart(charts.pay_by_group(view, "region_group"), "pay-region")
    st.subheader("Pay by seniority")
    show_chart(charts.pay_by_group(view, "seniority"), "pay-seniority")
    st.subheader("Where match and pay meet")
    st.caption("Top-right is the sweet spot: roles that pay well and fit your stack.")
    show_chart(charts.match_vs_pay(view), "match-pay")

    st.subheader("Most requested technologies")
    st.caption("Grey bars are skills that are not in MY_SKILLS (src/jobdash/config.py).")
    show_chart(charts.tech_demand(view_stack, MY_SKILLS), "tech")
    st.subheader("What each region asks for")
    show_chart(charts.tech_region_heatmap(view_stack, view), "tech-region",
               "Needs at least one region with 5 or more jobs in this selection.")

    a, b = st.columns(2)
    with a:
        st.subheader("Funding stage × team size")
        show_chart(charts.stage_by_size(view), "stage-size")
    with b:
        st.subheader("Companies with the most roles")
        show_chart(charts.bar_ranked(view["company"].value_counts().head(15), height=420),
                   "companies")
    st.subheader("Postings with an exact date")
    st.caption(f"{(view['posted_precision'] == 'day').sum()} of {len(view)} jobs give a day; "
               "the rest only say 'October 2026'.")
    show_chart(charts.posted_timeline(view), "timeline", "No job in this selection gives an exact date.")

# ---------------------------------------------------------- data quality
with t_quality:
    st.caption("A dashboard is only as honest as its data. This tab shows what cleaning had to fix.")
    q = st.columns(4)
    q[0].metric("Duplicate rows merged", len(raw) - len(jobs))
    q[1].metric("Shifted rows repaired", int(raw["was_repaired"].sum()))
    q[2].metric("Pay outliers", int(jobs["pay_outlier"].sum()))
    q[3].metric("No exact date", int((jobs["posted_precision"] != "day").sum()))
    a, b = st.columns(2)
    with a:
        st.subheader("How full each column is (raw rows)")
        show_chart(charts.completeness(raw), "completeness")
    with b:
        st.subheader("Pay outliers (Tukey's rule)")
        st.dataframe(jobs.loc[jobs["pay_outlier"], ["company", "compensation", "pay_mid_eur"]],
                     hide_index=True, width="stretch")
        st.subheader("Rows per tab")
        st.dataframe(raw["source_sheet"].value_counts().rename("rows"), width="stretch")
