from __future__ import annotations

import sys
from pathlib import Path

import polars as pl
import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
sys.path.insert(0, str(EXAMPLES))


@pytest.fixture
def examples() -> Path:
    return EXAMPLES


@pytest.fixture
def good_df() -> pl.DataFrame:
    from make_samples import build_good

    return pl.DataFrame(build_good())


@pytest.fixture
def bad_df() -> pl.DataFrame:
    from make_samples import build_bad, build_good

    return pl.DataFrame(build_bad(build_good()))
