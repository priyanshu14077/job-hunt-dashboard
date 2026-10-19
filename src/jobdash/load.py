"""Step 1 - Extract: read every tab of the workbook into ONE long DataFrame.

Concepts (see LEARN.md, lesson 1):
- Each tab has its own column names for the same idea ("Role", "Job Title").
  We map them onto one canonical schema so the tabs can be stacked (pd.concat).
- pandas reads a formula cell's cached *display text* ("Apply Now"), not the
  URL inside =HYPERLINK(...). openpyxl can read the formula itself, so we use it.
"""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path

import openpyxl
import pandas as pd

SHEET_ID = "1vhHpX-y_4Rg0Ntb2pH_x64XOBgPe3yhZPnTMeSxPFzg"
EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"
RAW_PATH = Path(__file__).resolve().parents[2] / "data" / "raw" / "jobs.xlsx"

CANONICAL = [
    "company", "title", "location", "remote_policy", "compensation",
    "tech_stack", "fit_notes", "summary", "apply_url", "date_posted",
    "job_id", "level", "team_size", "region",
]

# Ordered rules: the first matching keyword wins, so the specific ones come first.
# "Role Category & Level" must hit "level" before the bare "role" rule sees it.
HEADER_RULES: list[tuple[str, str]] = [
    ("no.", "drop"),
    ("company", "company"),
    ("category & level", "level"),
    ("experience level", "level"),
    ("team size", "team_size"),
    ("requisition", "job_id"),
    ("date posted", "date_posted"),
    ("compensation", "compensation"),
    ("tech stack", "tech_stack"),
    ("summary", "summary"),
    ("apply", "apply_url"),
    ("why", "fit_notes"),
    ("match", "fit_notes"),
    ("fit", "fit_notes"),
    ("job title", "title"),
    ("role", "title"),
    ("remote", "remote_policy"),
    ("country", "location"),
    ("hub", "location"),
    ("region", "region"),
]

HYPERLINK_RE = re.compile(r'HYPERLINK\(\s*"([^"]+)"', re.IGNORECASE)


def download(dest: Path = RAW_PATH) -> Path:
    """Fetch a fresh .xlsx export (works because the sheet is link-shared)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(EXPORT_URL, dest)
    return dest


def canonical_name(header: str) -> str:
    h = str(header).strip().lower()
    # "Location / Remote Policy" is mostly a location string; keep it as one.
    if h.startswith("location"):
        return "location"
    for keyword, name in HEADER_RULES:
        if keyword in h:
            return name
    raise KeyError(f"No rule for header {header!r}; add one to HEADER_RULES")


def _hyperlinks(ws) -> list[str | None]:
    """URL for each data row, read from whichever column holds HYPERLINK()."""
    urls: list[str | None] = []
    for row in ws.iter_rows(min_row=2):
        url = None
        for cell in row:
            if cell.hyperlink is not None:
                url = cell.hyperlink.target
            elif isinstance(cell.value, str) and (m := HYPERLINK_RE.search(cell.value)):
                url = m.group(1)
        urls.append(url)
    return urls


# "Type sniffers": a cheap test of whether a cell looks like it belongs in a column.
MONEY_RE = r"[\$€£₹¥]|kr\.|\b(?:USD|EUR|GBP|INR|SGD|AUD|JPY|SEK|DKK|NOK)\b"
SNIFFERS = {
    "compensation": MONEY_RE,
    "date_posted": r"20\d\d|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)",
    "team_size": r"team|employees|Seed|Series|Scaleup|Unicorn|Stealth",
    "remote_policy": r"Remote|Hybrid|On-?site|Office",
    "apply_url": r"^Apply",
}


def _row_score(values: pd.Series) -> int:
    """+1 for each cell that passes its sniffer, -1 for each that fails."""
    return sum(
        1 if re.search(pattern, str(values[col])) else -1
        for col, pattern in SNIFFERS.items()
        if col in values.index and pd.notna(values[col])
    )


def repair_shifted_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Fix rows where one cell was skipped and everything after it slid left.

    Symptom: the compensation column holds a tech stack while the column just
    before it holds the money. We try re-inserting the missing cell at each
    position and keep the version that scores best. Ties go to the smallest
    shift (the gap closest to compensation), so we move as few cells as possible.
    """
    repaired = pd.Series(False, index=df.index)
    if "compensation" not in df.columns:
        return df, repaired
    df = df.copy()
    cols = list(df.columns)
    k = cols.index("compensation")
    looks_like_money = df["compensation"].fillna("").str.contains(MONEY_RE)
    for i in df.index[~looks_like_money]:
        row = df.loc[i]
        best, best_score = row, _row_score(row)
        first = max(cols.index("company"), cols.index("title")) + 1  # anchors stay put
        for j in range(k, first - 1, -1):
            shifted = row.copy()
            shifted.iloc[j + 1 :] = row.iloc[j:-1].to_numpy()
            shifted.iloc[j] = None
            if (score := _row_score(shifted)) > best_score:
                best, best_score = shifted, score
        if best is not row:
            df.loc[i] = best
            repaired[i] = True
    return df, repaired


def load_raw(path: Path = RAW_PATH) -> pd.DataFrame:
    """All tabs stacked, canonical column names, plus `source_sheet` and `apply_url`."""
    if not path.exists():
        download(path)
    wb = openpyxl.load_workbook(path)  # formulas, not cached values
    frames = []
    for sheet_name, df in pd.read_excel(path, sheet_name=None, dtype=str).items():
        df = df.dropna(how="all")
        df.columns = [canonical_name(c) for c in df.columns]
        df = df.drop(columns=["drop"], errors="ignore")
        # Two headers can land on one name (e.g. two "fit" columns); keep the first.
        df = df.loc[:, ~df.columns.duplicated()]
        df, df["was_repaired"] = repair_shifted_rows(df)
        # df's index is still the original row position (dropna keeps it),
        # so reindex lines each URL up with its row even after blank rows go.
        df["apply_url"] = pd.Series(_hyperlinks(wb[sheet_name])).reindex(df.index)
        df["source_sheet"] = sheet_name
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    # Tabs that lack a column get NaN after concat; reindex fixes the order.
    return out.reindex(columns=CANONICAL + ["source_sheet", "was_repaired"])
