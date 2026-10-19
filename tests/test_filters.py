import pandas as pd
import pytest

from jobdash.filters import SORTS, Criteria, filter_jobs


def test_no_filters_keeps_everything(data):
    _, jobs, _ = data
    assert len(filter_jobs(jobs, Criteria())) == len(jobs)


def test_search_is_case_insensitive_and_ands_words(data):
    _, jobs, _ = data
    one = filter_jobs(jobs, Criteria(search="PYTHON"))
    both = filter_jobs(jobs, Criteria(search="python remote"))
    assert 0 < len(both) <= len(one) < len(jobs)


def test_search_with_regex_characters_does_not_crash(data):
    _, jobs, _ = data
    for text in ["C++", "(", "[", "$100k", "*", "\\", "node.js", "   "]:
        filter_jobs(jobs, Criteria(search=text))


def test_techs_require_all(data):
    _, jobs, _ = data
    out = filter_jobs(jobs, Criteria(techs=["Python", "Go"]))
    assert len(out) > 0
    assert out["stack"].map(lambda s: {"Python", "Go"} <= set(s)).all()


def test_impossible_combination_is_empty_not_error(data):
    _, jobs, _ = data
    out = filter_jobs(jobs, Criteria(search="zzzz-no-such-job"))
    assert out.empty


def test_pay_range_drops_unknown_pay(data):
    _, jobs, _ = data
    out = filter_jobs(jobs, Criteria(pay_range_k=(50, 60)))
    assert out["pay_mid_eur"].between(50_000, 60_000).all()


@pytest.mark.parametrize("sort", list(SORTS) + ["not a real sort"])
def test_every_sort(data, sort):
    _, jobs, _ = data
    assert len(filter_jobs(jobs, Criteria(sort=sort))) == len(jobs)
