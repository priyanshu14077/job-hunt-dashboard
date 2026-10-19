import pytest

from jobdash.clean import build
from jobdash.load import RAW_PATH, load_raw


@pytest.fixture(scope="session")
def data():
    if not RAW_PATH.exists():
        pytest.skip("data/raw/jobs.xlsx not downloaded yet")
    raw = load_raw()
    jobs, stack_long = build(raw)
    return raw, jobs, stack_long
