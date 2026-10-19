"""Step 4 - Visualise: one function per chart, each taking a tidy DataFrame.

Design rules applied here (LEARN.md, lesson 5):
- One series gets one colour and no legend; the title names it.
- Bars are sorted by value so the eye reads a ranking without effort.
- Magnitude uses a single-hue light->dark ramp, never a rainbow.
- Grid and axes stay quiet; the data is the loudest thing on the chart.

Every function returns None when there is too little data to draw honestly;
app.py shows a short message instead of an empty or misleading chart.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

BLUE = "#2a78d6"       # categorical slot 1: the main series
ORANGE = "#eb6834"     # slot 2: the comparison series
MUTED = "#a3a29c"      # "not you / everything else"
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def _style(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=8, b=8), bargap=0.25,
        hoverlabel=dict(font_size=13), legend_title_text="",
    )
    fig.update_xaxes(showgrid=False, title_text="")
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.15)", title_text="")
    return fig


def bar_ranked(counts: pd.Series, value_label: str = "Jobs", height: int = 360) -> go.Figure | None:
    """Horizontal ranked bars: the default answer to 'which is biggest?'."""
    counts = counts[counts > 0]
    if counts.empty:
        return None
    data = counts.sort_values().rename_axis("label").reset_index(name="value")
    fig = px.bar(data, x="value", y="label", orientation="h", text="value",
                 color_discrete_sequence=[BLUE], labels={"value": value_label, "label": ""})
    fig.update_traces(textposition="outside", cliponaxis=False,
                      hovertemplate="%{y}: %{x}<extra></extra>", marker_cornerradius=4)
    fig = _style(fig, height)
    fig.update_xaxes(showticklabels=False)
    fig.update_yaxes(showgrid=False)
    return fig


def posted_timeline(jobs: pd.DataFrame) -> go.Figure | None:
    dated = jobs.loc[jobs["posted_precision"] == "day"]
    if dated.empty:
        return None
    daily = dated.groupby(dated["posted"].dt.date).size().rename("Jobs").reset_index()
    fig = px.bar(daily, x="posted", y="Jobs", color_discrete_sequence=[BLUE])
    fig.update_traces(hovertemplate="%{x|%b %d}: %{y} jobs<extra></extra>", marker_cornerradius=4)
    return _style(fig, 280)


def pay_by_group(jobs: pd.DataFrame, group: str, min_n: int = 5) -> go.Figure | None:
    """A box shows the spread; the points show every job behind it.
    Sorted by median so the ranking reads top-down. Groups with fewer than
    min_n jobs are dropped: a 'median' of one job is not a distribution."""
    d = jobs[jobs["pay_mid_eur"].notna() & ~jobs["pay_outlier"]].copy()
    d[group] = d[group].astype(str)
    n = d.groupby(group)[group].transform("size")
    d = d[n >= min_n]
    if d.empty:
        return None
    d[group] = d[group] + " (n=" + n[n >= min_n].astype(str) + ")"
    order = d.groupby(group, observed=True)["pay_mid_eur"].median().sort_values().index.tolist()
    fig = px.box(d, x="pay_mid_eur", y=group, points="all", orientation="h",
                 category_orders={group: order[::-1]}, color_discrete_sequence=[BLUE],
                 hover_data={"company": True, "title": True, "pay_mid_eur": ":,.0f"},
                 labels={"pay_mid_eur": "Midpoint pay (EUR / yr)", group: ""})
    fig.update_traces(marker=dict(size=6, opacity=0.55), jitter=0.4, pointpos=0, line_width=1.5)
    fig = _style(fig, 60 + 52 * len(order))
    fig.update_xaxes(tickprefix="€", tickformat="~s", showgrid=True,
                     gridcolor="rgba(128,128,128,0.15)")
    fig.update_yaxes(showgrid=False)
    return fig


def match_vs_pay(jobs: pd.DataFrame) -> go.Figure | None:
    d = jobs[jobs["pay_mid_eur"].notna() & jobs["skill_match_pct"].notna() & ~jobs["pay_outlier"]]
    if d.empty:
        return None
    # Fixed category order -> each level always gets the same colour, whatever the filter.
    levels = list(jobs["seniority"].cat.categories)
    fig = px.scatter(d, x="skill_match_pct", y="pay_mid_eur", color="seniority",
                     category_orders={"seniority": levels},
                     color_discrete_map=dict(zip(levels, [BLUE, ORANGE, "#1baf7a", "#6250d6"])),
                     hover_data={"company": True, "title": True, "seniority": False,
                                 "pay_mid_eur": ":,.0f", "skill_match_pct": ":.0f"},
                     labels={"skill_match_pct": "Skill match (%)", "pay_mid_eur": "Pay (EUR)"})
    fig.update_traces(marker=dict(size=9, opacity=0.75, line=dict(width=1.5, color="white")))
    fig = _style(fig, 420)
    fig.update_xaxes(title_text="Your skill match (%)", showgrid=True,
                     gridcolor="rgba(128,128,128,0.15)")
    fig.update_yaxes(title_text="Midpoint pay (EUR / yr)", tickprefix="€", tickformat="~s")
    fig.update_layout(legend=dict(orientation="h", y=1.08, x=0))
    return fig


def tech_demand(stack_long: pd.DataFrame, my_skills: list[str], top: int = 20) -> go.Figure | None:
    """Top technologies, coloured by one question: do you have it?"""
    mine = {s.lower() for s in my_skills}
    counts = stack_long["tech"].value_counts().head(top).sort_values()
    if counts.empty:
        return None
    top = len(counts)
    d = counts.rename_axis("tech").reset_index(name="jobs")
    d["You"] = d["tech"].str.lower().isin(mine).map({True: "In your skills", False: "Gap"})
    fig = px.bar(d, x="jobs", y="tech", orientation="h", color="You", text="jobs",
                 color_discrete_map={"In your skills": BLUE, "Gap": MUTED},
                 category_orders={"tech": d["tech"].tolist()[::-1]})
    fig.update_traces(textposition="outside", cliponaxis=False, marker_cornerradius=4,
                      hovertemplate="%{y}: %{x} jobs<extra></extra>")
    fig = _style(fig, 26 * top + 90)
    fig.update_xaxes(showticklabels=False)
    fig.update_yaxes(showgrid=False)
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
                      margin=dict(t=36))
    return fig


def tech_region_heatmap(stack_long: pd.DataFrame, jobs: pd.DataFrame, top: int = 12,
                        min_n: int = 5) -> go.Figure | None:
    """Share of each region's jobs that ask for a technology.
    Shares, not counts: Europe has more jobs, so raw counts would just repeat that.
    Regions with fewer than min_n jobs are left out; 1 of 1 = 100% says nothing."""
    per_region = jobs.groupby("region_group").size().sort_values(ascending=False)
    per_region = per_region[per_region >= min_n]
    stack_long = stack_long[stack_long["region_group"].isin(per_region.index)]
    if stack_long.empty:
        return None
    top_tech = stack_long["tech"].value_counts().head(top).index
    top = len(top_tech)
    hits = (stack_long[stack_long["tech"].isin(top_tech)]
            .pivot_table(index="tech", columns="region_group", values="job_key",
                         aggfunc="nunique", fill_value=0))
    hits = hits.reindex(columns=per_region.index, fill_value=0)
    share = (hits / per_region * 100).round(0).loc[top_tech]
    share.columns = [f"{r} (n={per_region[r]})" for r in share.columns]
    fig = px.imshow(share, text_auto=".0f", aspect="auto", color_continuous_scale=SEQUENTIAL,
                    labels=dict(color="% of jobs", x="", y=""))
    fig.update_traces(hovertemplate="%{y} in %{x}: %{z:.0f}% of jobs<extra></extra>")
    return _style(fig, 34 * top + 80)


def stage_by_size(jobs: pd.DataFrame) -> go.Figure | None:
    t = pd.crosstab(jobs["stage"], jobs["headcount_band"])
    t = t.loc[t.sum(axis=1) > 0, t.sum(axis=0) > 0]
    if t.empty:
        return None
    fig = px.imshow(t, text_auto=True, aspect="auto", color_continuous_scale=SEQUENTIAL,
                    labels=dict(color="Jobs", x="Headcount", y="Stage"))
    fig.update_traces(hovertemplate="%{y}, %{x} people: %{z} jobs<extra></extra>")
    return _style(fig, 380)


def completeness(raw: pd.DataFrame) -> go.Figure | None:
    pct = (raw.notna().mean() * 100).round(0).drop(["source_sheet", "was_repaired"])
    fig = bar_ranked(pct, "% filled", 420)
    return fig.update_traces(texttemplate="%{x:.0f}%") if fig else None
