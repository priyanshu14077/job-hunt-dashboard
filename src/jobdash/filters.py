"""Step 3 - Slice: turn the user's filter choices into one boolean mask.

Kept separate from app.py so it can be tested without running Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

SEARCH_COLUMNS = ["company", "title", "tech_stack", "location", "remote_policy", "fit_notes"]

SORTS = {
    "Best skill match": (["skill_match_pct", "pay_mid_eur"], [False, False]),
    "Highest pay": (["pay_mid_eur"], [False]),
    "Newest": (["posted", "skill_match_pct"], [False, False]),
    "Listed in most tabs": (["listed_in_tabs", "skill_match_pct"], [False, False]),
    "Company A-Z": (["company", "title"], [True, True]),
}


@dataclass
class Criteria:
    search: str = ""
    regions: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    seniority: list[str] = field(default_factory=list)
    remote: list[str] = field(default_factory=list)
    stages: list[str] = field(default_factory=list)
    techs: list[str] = field(default_factory=list)      # job must list ALL of these
    pay_range_k: tuple[int, int] | None = None          # None = don't filter on pay
    min_match: int = 0
    hide_outliers: bool = False
    sort: str = "Best skill match"


def filter_jobs(jobs: pd.DataFrame, c: Criteria) -> pd.DataFrame:
    # Start with "keep everything" and AND each active filter into the mask.
    # An empty selection means "no filter", not "match nothing".
    mask = np.ones(len(jobs), dtype=bool)

    if c.search.strip():
        haystack = jobs[SEARCH_COLUMNS].fillna("").astype(str).agg(" ".join, axis=1).str.lower()
        for word in c.search.lower().split():
            mask &= haystack.str.contains(word, regex=False).to_numpy()

    for column, chosen in [("region_group", c.regions), ("country", c.countries),
                           ("seniority", c.seniority), ("remote_type", c.remote),
                           ("stage", c.stages)]:
        if chosen:
            mask &= jobs[column].astype(str).isin(chosen).to_numpy()

    if c.techs:
        wanted = {t.lower() for t in c.techs}
        mask &= jobs["stack"].map(lambda tags: wanted <= {t.lower() for t in tags}).to_numpy()

    if c.pay_range_k is not None:
        lo, hi = c.pay_range_k
        pay_k = jobs["pay_mid_eur"] / 1000
        mask &= pay_k.between(lo, hi).fillna(False).to_numpy()

    if c.min_match > 0:
        mask &= (jobs["skill_match_pct"].fillna(0) >= c.min_match).to_numpy()

    if c.hide_outliers:
        mask &= ~jobs["pay_outlier"].fillna(False).to_numpy()

    by, ascending = SORTS.get(c.sort, SORTS["Best skill match"])
    return jobs[mask].sort_values(by, ascending=ascending, na_position="last")
