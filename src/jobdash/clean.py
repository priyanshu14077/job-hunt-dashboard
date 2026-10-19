"""Step 2 - Transform: turn free-text cells into typed, analysable columns.

Every function here takes a Series of strings and returns typed data, so each
one can be tested and learned on its own (see LEARN.md, lessons 2-4).
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .config import FX_TO_EUR, MY_SKILLS, STACK_ALIASES

# ---------------------------------------------------------------- compensation

CURRENCY_CODES = r"\b(USD|EUR|GBP|INR|SGD|AUD|HKD|JPY|SEK|DKK|NOK|CHF|CAD|PLN)\b"
# Longest symbols first: "A$" must win over "$".
CURRENCY_SYMBOLS = [("HK$", "HKD"), ("A$", "AUD"), ("S$", "SGD"), ("$", "USD"), ("€", "EUR"),
                    ("£", "GBP"), ("₹", "INR"), ("¥", "JPY")]
NUMBER_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*([kK])?")


def _first_range(text: str) -> str:
    """'£65k - £95k GBP / ~€75k EUR + Equity' -> '£65k - £95k GBP'."""
    return re.split(r"\s/\s|\(|\+\s|\bEquity\b", text, maxsplit=1)[0]


def parse_compensation(text) -> dict:
    out = {"currency": None, "pay_min": np.nan, "pay_max": np.nan, "monthly": False}
    if not isinstance(text, str):
        return out
    seg = _first_range(text)
    if m := re.search(CURRENCY_CODES, seg):
        out["currency"] = m.group(1)
    else:
        out["currency"] = next((code for sym, code in CURRENCY_SYMBOLS if sym in seg), None)
    nums = []
    for digits, k in NUMBER_RE.findall(seg):
        value = float(digits.replace(",", ""))  # also handles Indian 20,00,000
        nums.append(value * 1000 if k else value)
    if nums:
        out["pay_min"], out["pay_max"] = nums[0], nums[1] if len(nums) > 1 else nums[0]
    out["monthly"] = bool(re.search(r"/\s*mo(?:nth)?\b|per month", text, re.I))
    return out


def add_compensation(df: pd.DataFrame) -> pd.DataFrame:
    parsed = pd.DataFrame(df["compensation"].map(parse_compensation).tolist(), index=df.index)
    df = df.join(parsed)
    df["has_equity"] = df["compensation"].str.contains("equity|stock", case=False, na=False)
    # Vectorised NumPy maths: no Python loop, the whole column at once.
    fx = df["currency"].map(FX_TO_EUR).astype(float)
    months = np.where(df["monthly"], 12, 1)
    df["pay_min_eur"] = df["pay_min"] * fx * months
    df["pay_max_eur"] = df["pay_max"] * fx * months
    df["pay_mid_eur"] = (df["pay_min_eur"] + df["pay_max_eur"]) / 2
    df["pay_spread_pct"] = (df["pay_max_eur"] / df["pay_min_eur"] - 1) * 100
    return df


def flag_outliers(s: pd.Series, k: float = 1.5) -> pd.Series:
    """Tukey's rule: outside [Q1 - k*IQR, Q3 + k*IQR] is an outlier."""
    q1, q3 = np.nanpercentile(s, [25, 75])
    iqr = q3 - q1
    return (s < q1 - k * iqr) | (s > q3 + k * iqr)


# ----------------------------------------------------------------------- dates

DAY_RE = r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+20\d\d|20\d\d-\d\d-\d\d)"
MONTH_RE = r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+20\d\d)"


def parse_posted(date_col: pd.Series, fallback: pd.Series) -> pd.DataFrame:
    """Dates come as '2026-10-12', 'Oct 15, 2026 (3 days ago)', 'October 2026',
    or buried in the remote-policy text of one tab. Returns date + precision."""
    text = date_col.fillna(fallback).fillna("")
    day = pd.to_datetime(text.str.extract(DAY_RE)[0], format="mixed", errors="coerce")
    month = pd.to_datetime(text.str.extract(MONTH_RE)[0], format="mixed", errors="coerce")
    precision = np.select([day.notna(), month.notna()], ["day", "month"], default="unknown")
    return pd.DataFrame({"posted": day.fillna(month), "posted_precision": precision})


# ---------------------------------------------------------------- geography

COUNTRY_KEYWORDS = {
    "Sweden": ["sweden", "stockholm", "gothenburg", "malmö", "malmo"],
    "Denmark": ["denmark", "copenhagen", "aarhus"],
    "Norway": ["norway", "oslo"],
    "Finland": ["finland", "helsinki", "espoo"],
    "Estonia": ["estonia", "tallinn"],
    "United Kingdom": ["uk", "london", "united kingdom", "manchester", "edinburgh"],
    "Germany": ["germany", "berlin", "munich", "hamburg"],
    "France": ["france", "paris"],
    "Netherlands": ["netherlands", "amsterdam"],
    "Ireland": ["ireland", "dublin"],
    "Switzerland": ["switzerland", "zurich"],
    "Spain": ["spain", "barcelona", "madrid"],
    "Portugal": ["portugal", "lisbon"],
    "Poland": ["poland", "warsaw", "krakow"],
    "Austria": ["austria", "vienna"],
    "Czechia": ["czech", "prague"],
    "Italy": ["italy", "milan", "rome"],
    "Singapore": ["singapore"],
    "Australia": ["australia", "sydney", "melbourne", "brisbane", "perth"],
    "New Zealand": ["new zealand", "auckland"],
    "Japan": ["japan", "tokyo"],
    "Hong Kong": ["hong kong"],
    "India": ["india", "bengaluru", "bangalore", "delhi", "mumbai", "hyderabad", "pune"],
    "United States": ["us", "usa", "united states", "san francisco", "new york", "nyc",
                      "seattle", "austin", "boston", "sf"],
    "Canada": ["canada", "toronto", "vancouver"],
}
REGION_OF = {
    **dict.fromkeys(["Sweden", "Denmark", "Norway", "Finland"], "Nordics"),
    **dict.fromkeys(["Estonia", "Germany", "France", "Netherlands", "Ireland", "Switzerland",
                     "Spain", "Portugal", "Poland", "Austria", "Czechia", "Italy", "United Kingdom"],
                    "Europe"),
    **dict.fromkeys(["United States", "Canada"], "North America"),
    **dict.fromkeys(["Australia", "New Zealand"], "Australia & NZ"),
    **dict.fromkeys(["Singapore", "Japan", "India", "Hong Kong"], "Asia"),
}


def find_country(text) -> str | None:
    if not isinstance(text, str):
        return None
    low = text.lower()
    # Earliest mention wins: "London / Tallinn" is London-based.
    hits = []
    for country, words in COUNTRY_KEYWORDS.items():
        for w in words:
            if m := re.search(rf"\b{re.escape(w)}\b", low):
                hits.append((m.start(), country))
    return min(hits)[1] if hits else None


def add_geography(df: pd.DataFrame) -> pd.DataFrame:
    where = df["location"].fillna("") + " | " + df["remote_policy"].fillna("")
    df["country"] = where.map(find_country)
    df["region_group"] = df["country"].map(REGION_OF)
    remote_text = where.str.lower()
    # No city or country named: fall back to the remote zone ("Remote EMEA").
    for pattern, region in [("europe|emea", "Europe"), ("apac|asia", "Asia")]:
        df.loc[df["region_group"].isna() & remote_text.str.contains(pattern), "region_group"] = region
    df["region_group"] = df["region_group"].fillna("Global / Other")
    return df


def remote_type(text: pd.Series) -> pd.Series:
    """np.select = vectorised if/elif/else. The first true condition wins."""
    t = text.fillna("").str.lower()
    conditions = [
        t.str.contains(r"on-?site|in-office|office only"),
        t.str.contains(r"hybrid"),
        t.str.contains(r"100% remote|fully remote|remote only|remote-first|^remote"),
        t.str.contains(r"remote"),
    ]
    choices = ["On-site", "Hybrid", "Fully remote", "Remote-friendly"]
    return pd.Series(np.select(conditions, choices, default="Not stated"), index=text.index)


# ------------------------------------------------------------ company shape

STAGES = ["Stealth", "Pre-seed", "Seed", "Series A", "Series B", "Series C", "Series D",
          "Series E", "Unicorn", "Scaleup", "Public"]


def add_company_shape(df: pd.DataFrame) -> pd.DataFrame:
    text = df["team_size"].fillna("") + " " + df["level"].fillna("")
    # "11-50 employees" -> midpoint 30.5; "~60 team" -> 60
    rng = text.str.extract(r"(\d+)\s*-\s*(\d+)\s*(?:employees|team|people)").astype(float)
    approx = text.str.extract(r"~\s*(\d[\d,]*)")[0].str.replace(",", "").astype(float)
    df["headcount"] = approx.fillna(rng.mean(axis=1, skipna=False))
    df["headcount_band"] = pd.cut(
        df["headcount"], bins=[0, 20, 50, 150, 500, np.inf],
        labels=["1-20", "21-50", "51-150", "151-500", "500+"],
    )
    stage = text.str.extract(r"(Stealth|Pre-seed|Seed|Series [A-E]|Unicorn|Scaleup|Public)",
                             flags=re.I)[0].str.title().str.replace("Pre-Seed", "Pre-seed")
    df["stage"] = pd.Categorical(stage, categories=STAGES, ordered=True)
    return df


def seniority(title: pd.Series, level: pd.Series) -> pd.Series:
    t = (title.fillna("") + " " + level.fillna("")).str.lower()
    conditions = [
        t.str.contains(r"intern|graduate|junior|entry|new grad|associate|engineer i\b|0-2"),
        t.str.contains(r"staff|principal|lead|head of|architect"),
        t.str.contains(r"senior|sr\.|iii\b"),
    ]
    out = np.select(conditions, ["Junior / Entry", "Staff+", "Senior"], default="Mid")
    order = ["Junior / Entry", "Mid", "Senior", "Staff+"]
    return pd.Series(pd.Categorical(out, categories=order, ordered=True), index=title.index)


# ---------------------------------------------------------------- tech stack

def normalise_tag(tag: str) -> str:
    tag = tag.strip().strip(".")
    return STACK_ALIASES.get(tag.lower(), tag)


def split_stack(text) -> list[str]:
    if not isinstance(text, str):
        return []
    tags = [normalise_tag(t) for t in re.split(r",|;", text) if t.strip()]
    return list(dict.fromkeys(t for t in tags if 1 < len(t) <= 40))  # dedupe, keep order


def skill_match(tags: list[str]) -> float:
    """Share of a role's stack you already have (0-100)."""
    if not tags:
        return np.nan
    mine = {s.lower() for s in MY_SKILLS}
    return 100 * np.mean([t.lower() in mine for t in tags])


# --------------------------------------------------------------------- dedupe

def job_key(company: pd.Series, title: pd.Series) -> pd.Series:
    """Normalise so 'Wise ' + 'Senior Backend Engineer (Payments)' match across tabs."""
    norm = lambda s: (s.fillna("").str.lower()
                      .str.replace(r"\(.*?\)", "", regex=True)
                      .str.replace(r"[^a-z0-9]+", " ", regex=True).str.strip())
    return norm(company) + " :: " + norm(title)


def build(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """raw rows (one per tab occurrence) -> (jobs, stack_long).

    jobs: one row per distinct job.  stack_long: one row per (job, tech tag),
    the 'tidy' shape that makes counting technologies a one-liner.
    """
    df = raw.copy()
    df["job_key"] = job_key(df["company"], df["title"])
    # How many tabs list the same job is a signal in itself.
    df["listed_in_tabs"] = df.groupby("job_key")["source_sheet"].transform("nunique")
    # groupby().first() takes the first NON-NULL value per column: a free coalesce
    # that merges what different tabs know about the same job.
    jobs = df.groupby("job_key", sort=False).first().reset_index()

    jobs = add_compensation(jobs)
    jobs["pay_outlier"] = flag_outliers(jobs["pay_mid_eur"])
    jobs = jobs.join(parse_posted(jobs["date_posted"], jobs["remote_policy"]))
    jobs = add_geography(jobs)
    jobs["remote_type"] = remote_type(jobs["remote_policy"].fillna(jobs["location"]))
    jobs = add_company_shape(jobs)
    jobs["seniority"] = seniority(jobs["title"], jobs["level"])
    jobs["stack"] = jobs["tech_stack"].map(split_stack)
    jobs["skill_match_pct"] = jobs["stack"].map(skill_match)

    stack_long = (jobs[["job_key", "company", "region_group", "seniority", "pay_mid_eur", "stack"]]
                  .explode("stack").dropna(subset=["stack"]).rename(columns={"stack": "tech"}))
    return jobs, stack_long
