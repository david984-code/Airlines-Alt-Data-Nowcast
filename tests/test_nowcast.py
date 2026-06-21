"""Unit tests for the nowcast statistics (no network)."""

import numpy as np
import pandas as pd

from src import nowcast as nc


def _periods(n: int, start_year: int = 2019) -> list[str]:
    out, y, q = [], start_year, 1
    for _ in range(n):
        out.append(f"{y}Q{q}")
        q = q + 1 if q < 4 else 1
        y = y if out[-1][-1] != "4" else y + 1
    return out


def test_deseasonalized_growth_strips_seasonality_and_trend():
    periods = _periods(24)
    seasonal = {1: 1.0, 2: 1.25, 3: 1.6, 4: 1.1}  # airlines peak in Q3 (summer)
    vals = [np.exp(0.02 * t) * seasonal[int(p[-1])] for t, p in enumerate(periods)]
    g = nc._deseasonalized_growth(pd.Series(vals, index=periods))
    assert g.std() < 1e-9
    assert abs(g.mean() - 0.02) < 1e-6


def test_deseasonalized_growth_needs_min_history():
    s = pd.Series([1, 2, 3, 4], index=_periods(4))
    assert nc._deseasonalized_growth(s).empty


def test_block_bootstrap_ci_perfect_corr_and_independent():
    rng = np.random.default_rng(1)
    a = rng.normal(size=40)
    lo, hi, p = nc._block_bootstrap_ci(a, a.copy())
    assert lo > 0.9 and p < 0.05
    b = rng.normal(size=40)
    lo2, hi2, p2 = nc._block_bootstrap_ci(a, b)
    assert lo2 < 0 < hi2 and p2 > 0.05
