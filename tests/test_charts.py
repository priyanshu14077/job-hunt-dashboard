"""Every chart must survive empty, single-row and odd selections."""
import pandas as pd
import pytest

from jobdash import board, charts
from jobdash.config import MY_SKILLS


def selections(jobs, stack_long):
    one = jobs.iloc[:1]
    no_pay = jobs.assign(pay_mid_eur=float("nan"), pay_min_eur=float("nan"), pay_max_eur=float("nan"))
    return {
        "all": (jobs, stack_long),
        "empty": (jobs.iloc[:0], stack_long.iloc[:0]),
        "one": (one, stack_long[stack_long.job_key.isin(one.job_key)]),
        "no_pay": (no_pay, stack_long),
        "no_stack": (jobs, stack_long.iloc[:0]),
    }


@pytest.mark.parametrize("case", ["all", "empty", "one", "no_pay", "no_stack"])
def test_charts_never_raise(data, case):
    raw, jobs, stack_long = data
    view, vstack = selections(jobs, stack_long)[case]
    figs = [
        charts.bar_ranked(view["region_group"].value_counts()),
        charts.posted_timeline(view),
        charts.pay_by_group(view, "region_group"),
        charts.pay_by_group(view, "seniority"),
        charts.match_vs_pay(view),
        charts.tech_demand(vstack, MY_SKILLS),
        charts.tech_region_heatmap(vstack, view),
        charts.stage_by_size(view),
        charts.completeness(raw),
    ]
    if case == "all":
        assert all(f is not None for f in figs)
    if case == "empty":
        assert all(f is None for f in figs[:-1])


def test_every_card_formats(data):
    _, jobs, _ = data
    for _, job in jobs.iterrows():
        for text in (board.meta_line(job), board.pay_line(job), board.posted_label(job),
                     board.tech_badges(job["stack"], MY_SKILLS), board.md(job["fit_notes"])):
            assert isinstance(text, str) and "nan" not in text.lower().split()


def test_md_escapes_dollar_signs():
    assert board.md("$140,000 - $285,000") == r"\$140,000 \- \$285,000"
    assert board.md(None) == "" and board.md(float("nan")) == ""
