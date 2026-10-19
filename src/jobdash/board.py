"""Text for one job card. Pure functions, so they're easy to test.

Streamlit renders card text as Markdown, where "$...$" becomes a LaTeX formula
and "_x_" becomes italics. Sheet text like "$140,000 - $285,000" would come out
garbled, so every value from the sheet goes through md() first.
"""

from __future__ import annotations

import re

import pandas as pd

_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]<>()#+\-.!|$~:])")


def md(value) -> str:
    """Escape sheet text for Markdown; empty or NaN becomes ''."""
    if value is None or (not isinstance(value, (list, tuple)) and pd.isna(value)):
        return ""
    return _MD_SPECIAL.sub(r"\\\1", str(value).strip())


def money_k(eur) -> str:
    return "" if pd.isna(eur) else f"€{eur / 1000:,.0f}k"


def pay_line(job: pd.Series) -> str:
    lo, hi = money_k(job.get("pay_min_eur")), money_k(job.get("pay_max_eur"))
    if not lo:
        return "Pay not listed"
    span = lo if lo == hi else f"{lo} – {hi}"
    extras = " · equity" if job.get("has_equity") else ""
    return f"{span} / yr{extras}"


def meta_line(job: pd.Series) -> str:
    """Location · remote · seniority · stage · size, skipping blanks."""
    where = job.get("country") or job.get("region_group")
    stage = job.get("stage")
    size = job.get("headcount")
    parts = [
        where if isinstance(where, str) else "",
        job.get("remote_type") if job.get("remote_type") != "Not stated" else "",
        str(job.get("seniority") or ""),
        str(stage) if pd.notna(stage) else "",
        f"~{size:,.0f} people" if pd.notna(size) else "",
    ]
    return " · ".join(md(p) for p in parts if p)


def posted_label(job: pd.Series) -> str:
    when = job.get("posted")
    if pd.isna(when):
        return "Date not given"
    if job.get("posted_precision") == "month":
        return f"Posted {when:%B %Y}"
    return f"Posted {when:%b %d, %Y}"


def tech_badges(tags: list[str], my_skills: list[str], limit: int = 10) -> str:
    """Blue badge = you have it, grey = a gap. Uses Streamlit's :color-badge[] syntax."""
    if not isinstance(tags, list) or not tags:
        return ""
    mine = {s.lower() for s in my_skills}
    shown = [f":{'blue' if t.lower() in mine else 'gray'}-badge[{md(t)}]" for t in tags[:limit]]
    more = len(tags) - limit
    return " ".join(shown) + (f" +{more} more" if more > 0 else "")


def is_url(value) -> bool:
    return isinstance(value, str) and value.startswith(("http://", "https://"))
