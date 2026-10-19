"""Run the real app through many filter combinations; any exception fails.

Streamlit's AppTest executes app.py without a browser and lets us set widgets.
"""
import random
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def fresh():
    return AppTest.from_file(APP, default_timeout=120).run()


def widget(at, kind, label):
    return next(w for w in getattr(at, kind) if w.label == label)


def assert_ok(at):
    assert not at.exception, [e.value for e in at.exception]


def test_default_view():
    at = fresh()
    assert_ok(at)
    assert at.metric[0].value.endswith(f"of {at.metric[0].value.split()[-1]}")


@pytest.mark.parametrize("label", ["Region", "Country", "Seniority", "Remote", "Funding stage"])
def test_each_single_option(label):
    at = fresh()
    for option in widget(at, "multiselect", label).options:
        widget(at, "multiselect", label).set_value([option]).run()
        assert_ok(at)


@pytest.mark.parametrize("text", ["python", "C++", "$", "(", "zzzz-nothing", "remote europe go", "  "])
def test_search(text):
    at = fresh()
    widget(at, "text_input", "Search").input(text).run()
    assert_ok(at)


def test_empty_result_shows_warning():
    at = fresh()
    widget(at, "text_input", "Search").input("zzzz-nothing").run()
    assert_ok(at)
    assert any("No jobs match" in w.value for w in at.warning)


def test_sliders_toggle_sort_and_pages():
    at = fresh()
    for sort in widget(at, "selectbox", "Sort by").options:
        widget(at, "selectbox", "Sort by").set_value(sort).run()
        assert_ok(at)
    widget(at, "slider", "Min skill match (%)").set_value(100).run()
    assert_ok(at)
    widget(at, "slider", "Min skill match (%)").set_value(0).run()
    pay = widget(at, "slider", "Pay midpoint (€k / yr)")
    pay.set_value((0, 5)).run()          # almost nothing earns under €5k
    assert_ok(at)
    widget(at, "slider", "Pay midpoint (€k / yr)").set_value((60, 90)).run()
    widget(at, "toggle", "Hide pay outliers").set_value(True).run()
    assert_ok(at)
    page = next(w for w in at.number_input if w.label.startswith("Page"))
    page.set_value(page.max).run()       # last page may be partly full
    assert_ok(at)


def test_tech_must_have():
    at = fresh()
    widget(at, "multiselect", "Must use (all of)").set_value(["Python"]).run()
    assert_ok(at)
    widget(at, "multiselect", "Must use (all of)").set_value(["Python", "Kotlin", "C++"]).run()
    assert_ok(at)


def test_random_combinations():
    rng = random.Random(7)
    at = fresh()
    labels = ["Region", "Country", "Seniority", "Remote", "Funding stage"]
    for _ in range(40):
        for label in labels:
            ms = widget(at, "multiselect", label)
            ms.set_value(rng.sample(ms.options, k=rng.choice([0, 0, 1, 2])))
        widget(at, "slider", "Min skill match (%)").set_value(rng.choice([0, 0, 40, 80]))
        at.run()
        assert_ok(at)


def test_table_view():
    at = fresh()
    at.button_group[0].set_value("Table").run()
    assert_ok(at)
    assert len(at.dataframe) >= 1
