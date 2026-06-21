"""Quarterly aggregation of TSA throughput and reported carrier traffic."""

from __future__ import annotations

import pandas as pd

import config

from .data import tsa


def tsa_quarterly(force: bool = False) -> pd.Series:
    """Total TSA throughput per complete calendar quarter, indexed 'YYYYQn'."""
    daily = tsa.fetch(force=force)
    q = pd.PeriodIndex(pd.DatetimeIndex(daily.index), freq="Q")
    days = daily.groupby(q).count()
    total = daily.groupby(q).sum()
    total = total[days >= 80]  # drop partial (current) quarter
    total.index = total.index.astype(str)
    total.index.name = "period"
    return total


def reported_quarterly(metric: str = "revenue_passenger_miles") -> pd.DataFrame:
    """Verified carrier KPI as a wide period x ticker frame (one metric)."""
    kpi = pd.read_csv(config.DATA_DIR / "kpi_ground_truth.csv")
    kpi = kpi[kpi["verified"] & (kpi["metric"] == metric)]
    wide = kpi.pivot_table(index="period", columns="ticker", values="value")
    return wide.sort_index()


# Carriers with clean, current coverage (AAL stops 2017, UAL 2022 -- format drift).
CORE_CARRIERS = ("LUV", "DAL", "ALK", "JBLU")


def industry_quarterly(
    metric: str = "revenue_passenger_miles", tickers: tuple[str, ...] = CORE_CARRIERS
) -> pd.Series:
    """Sum of the core carriers' KPI per quarter (quarters where all of them report)."""
    wide = reported_quarterly(metric)
    cols = [t for t in tickers if t in wide.columns]
    return wide[cols].dropna().sum(axis=1)


if __name__ == "__main__":
    t = tsa_quarterly()
    print(f"TSA quarterly: {len(t)} quarters, {t.index.min()} -> {t.index.max()}")
    print(t.tail())
