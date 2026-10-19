import numpy as np
import pandas as pd
import pytest

from jobdash.clean import find_country, parse_compensation, remote_type, split_stack
from jobdash.load import canonical_name, repair_shifted_rows


@pytest.mark.parametrize("text, currency, lo, hi, monthly", [
    ("$140,000 - $285,000+ USD + Significant Equity", "USD", 140_000, 285_000, False),
    ("£65k - £95k GBP / ~€75k - €110k EUR + Equity", "GBP", 65_000, 95_000, False),
    ("A$95,000 - A$130,000 AUD + Equity Options", "AUD", 95_000, 130_000, False),
    ("₹20,00,000 - ₹28,00,000 INR", "INR", 2_000_000, 2_800_000, False),
    ("kr.55k - kr.75k SEK/mo (~€65k - €90k/yr)", "SEK", 55_000, 75_000, True),
    ("HK$30,000 - HK$45,000/mo", "HKD", 30_000, 45_000, True),
    ("$40,000 - $65,000 USD + 0.5% - 2.0% Equity", "USD", 40_000, 65_000, False),
])
def test_parse_compensation(text, currency, lo, hi, monthly):
    out = parse_compensation(text)
    assert (out["currency"], out["pay_min"], out["pay_max"], out["monthly"]) == (currency, lo, hi, monthly)


def test_parse_compensation_missing():
    assert np.isnan(parse_compensation(None)["pay_min"])


def test_find_country_takes_earliest_mention():
    assert find_country("London / Tallinn, Estonia") == "United Kingdom"
    assert find_country("Remote EMEA / Worldwide") is None


def test_remote_type_first_match_wins():
    s = pd.Series(["Singapore / Hybrid-Remote", "100% Remote Worldwide", "Berlin / Remote Europe", None])
    assert remote_type(s).tolist() == ["Hybrid", "Fully remote", "Remote-friendly", "Not stated"]


def test_split_stack_normalises_aliases():
    assert split_stack("Go (Golang), Postgres, React.js, Python, Python") == ["Go", "PostgreSQL", "React", "Python"]


def test_header_rules():
    assert canonical_name("Role Category & Level (Junior / Graduate)") == "level"
    assert canonical_name("Role") == "title"
    assert canonical_name("Location / Remote Policy") == "location"


def test_repair_shifted_row():
    cols = ["company", "location", "title", "remote_policy", "compensation", "tech_stack", "apply_url"]
    good = ["A", "Berlin", "Eng", "Remote Europe", "€80k EUR", "Python", "Apply"]
    shifted = ["B", "Remote EMEA", "Eng", "$100k USD", "Go", "Apply", None]  # remote cell missing
    df, fixed = repair_shifted_rows(pd.DataFrame([good, shifted], columns=cols))
    assert fixed.tolist() == [False, True]
    assert df.loc[1, "compensation"] == "$100k USD" and df.loc[1, "apply_url"] == "Apply"
