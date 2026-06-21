"""The nowcast test: does TSA throughput growth lead reported carrier traffic?

Same methodology bar as the gig reader: the headline is the correlation of
*deseasonalized QoQ growth* (not co-trend-inflated levels-of-YoY) at lag 0 (the
contemporaneous, pre-earnings nowcast), with a paired 2-quarter block-bootstrap
CI and an ex-COVID robustness cut. TSA is industry-wide, so it should track the
industry aggregate tightest; a carrier's residual vs the TSA baseline is a
share/relative-value signal.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

import config

from .analysis import industry_quarterly, reported_quarterly, tsa_quarterly

_N_BOOT = 5000
_BLOCK = 2


def _deseasonalized_growth(s: pd.Series) -> pd.Series:
    """QoQ log-growth of a seasonally-adjusted series (OLS trend + quarter dummies)."""
    s = s.dropna()
    if len(s) < 8:
        return pd.Series(dtype=float)
    y = np.log(s.to_numpy())
    n = len(y)
    q = np.array([int(p[-1]) for p in s.index])
    dummies = np.column_stack([(q == k).astype(float) for k in (2, 3, 4)])
    x = np.column_stack([np.ones(n), np.arange(n), dummies])
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    return pd.Series(np.diff(y - dummies @ beta[2:]), index=s.index[1:])


def _block_bootstrap_ci(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    rng = np.random.default_rng(0)
    m = len(a)
    pool = np.arange(m - _BLOCK + 1)
    rs = np.empty(_N_BOOT)
    for i in range(_N_BOOT):
        idx = np.concatenate(
            [np.arange(s, s + _BLOCK) for s in rng.choice(pool, int(np.ceil(m / _BLOCK)))]
        )[:m]
        aa, bb = a[idx], b[idx]
        rs[i] = np.corrcoef(aa, bb)[0, 1] if aa.std() and bb.std() else 0.0
    rs = rs[~np.isnan(rs)]
    return (
        float(np.percentile(rs, 2.5)),
        float(np.percentile(rs, 97.5)),
        float(2 * min((rs <= 0).mean(), (rs >= 0).mean())),
    )


def _bridge(label: str, signal: pd.Series, target: pd.Series, since: str | None) -> dict:
    common = signal.index.intersection(target.index)
    if since:
        common = common[common >= since]
    gs = _deseasonalized_growth(signal.loc[common])
    gt = _deseasonalized_growth(target.loc[common])
    pair = pd.DataFrame({"s": gs, "t": gt}).dropna()  # lag-0 contemporaneous nowcast
    res: dict = {"label": label, "since": since, "n_quarters": int(len(common)), "n": len(pair)}
    if len(pair) >= 6:
        r = float(pair["s"].corr(pair["t"]))
        lo, hi, p = _block_bootstrap_ci(pair["s"].to_numpy(), pair["t"].to_numpy())
        res.update(r=r, ci95=[lo, hi], p_value=p, signal=bool(lo > 0 or hi < 0))
    return res


def run(metric: str = "revenue_passenger_miles") -> list[dict]:
    tsa = tsa_quarterly()
    bridges = [
        ("TSA -> industry RPMs", industry_quarterly(metric), None),
        ("TSA -> industry RPMs (ex-COVID)", industry_quarterly(metric), "2021Q1"),
    ]
    wide = reported_quarterly(metric)
    for carrier in [c for c in ("LUV", "DAL", "ALK", "JBLU") if c in wide.columns]:
        bridges.append((f"TSA -> {carrier} RPMs (ex-COVID)", wide[carrier].dropna(), "2021Q1"))

    results = [_bridge(lbl, tsa, tgt, since) for lbl, tgt, since in bridges]
    print(f"\nTSA -> reported {metric} (deseasonalized QoQ growth, lag 0)")
    print("=" * 64)
    for r in results:
        if "r" in r:
            flag = "SIGNAL" if r["signal"] else "none"
            print(
                f"  {r['label']:34} r={r['r']:+.2f}  CI=[{r['ci95'][0]:+.2f},{r['ci95'][1]:+.2f}]"
                f"  n={r['n']:>2}  {flag}"
            )
        else:
            print(f"  {r['label']:34} insufficient history (n={r['n']})")
    out = config.OUTPUT_DIR / "nowcast_results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out}")
    return results


if __name__ == "__main__":
    run()
