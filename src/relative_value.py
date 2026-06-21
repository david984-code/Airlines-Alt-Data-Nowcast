"""Within-subsector relative-value: carrier RPM growth vs the TSA baseline.

TSA is the industry demand baseline. A domestic carrier's deseasonalized RPM
growth MINUS its TSA-implied growth (OLS of carrier-growth on TSA-growth) is its
idiosyncratic *share* move -- gaining or losing traffic faster than the industry.

The pair thesis the L/S book wants: long the share-gainer, short the laggard. For
that to be tradeable the residual must PERSIST quarter-to-quarter. We test:
  1. pooled lag-1 autocorrelation of residuals (is share momentum real?);
  2. a rank pair test -- does residual[t] predict the realized residual *spread*
     at t+1 (top-ranked carrier minus bottom-ranked)?

Restricted to predominantly-domestic carriers (LUV/JBLU/ALK), where the residual
is share rather than the international traffic TSA cannot see (e.g. Delta). This
is a traffic-share read, NOT a stock-alpha claim; linking to relative stock
returns (beta-hedged) is the next step.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

import config

from .analysis import reported_quarterly, tsa_quarterly
from .nowcast import _deseasonalized_growth

DOMESTIC = ("LUV", "JBLU", "ALK")
_SINCE = "2021Q1"  # ex-COVID normal-times


def residuals(metric: str = "revenue_passenger_miles") -> pd.DataFrame:
    """Per-carrier share residual = deseasonalized RPM growth - TSA-implied."""
    tsa = _deseasonalized_growth(tsa_quarterly())
    wide = reported_quarterly(metric)
    out = {}
    for c in DOMESTIC:
        if c not in wide.columns:
            continue
        gr = _deseasonalized_growth(wide[c].dropna())
        pair = pd.DataFrame({"tsa": tsa, "rpm": gr}).dropna()
        pair = pair[pair.index >= _SINCE]
        if len(pair) < 8:
            continue
        b, a = np.polyfit(pair["tsa"], pair["rpm"], 1)
        out[c] = pair["rpm"] - (a + b * pair["tsa"])  # share residual
    return pd.DataFrame(out)


def _persistence(res: pd.DataFrame) -> dict:
    """Pooled lag-1 autocorrelation of residuals across carriers."""
    pairs = [
        (res[c].iloc[:-1].to_numpy(), res[c].shift(-1).dropna().to_numpy()) for c in res.columns
    ]
    a = np.concatenate([p[0] for p in pairs])
    b = np.concatenate([p[1] for p in pairs])
    rng = np.random.default_rng(0)
    idxs = rng.integers(0, len(a), (5000, len(a)))
    boot = np.array([np.corrcoef(a[ix], b[ix])[0, 1] for ix in idxs])
    boot = boot[~np.isnan(boot)]
    return {
        "n_pairs": int(len(a)),
        "lag1_autocorr": float(np.corrcoef(a, b)[0, 1]),
        "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
    }


def _rank_pair_test(res: pd.DataFrame) -> dict:
    """Does residual[t] rank predict the realized top-minus-bottom spread at t+1?"""
    spreads = []
    for i in range(len(res) - 1):
        now, nxt = res.iloc[i].dropna(), res.iloc[i + 1]
        if len(now) < 2:
            continue
        top, bot = now.idxmax(), now.idxmin()
        if pd.notna(nxt.get(top)) and pd.notna(nxt.get(bot)):
            spreads.append(nxt[top] - nxt[bot])  # long gainer / short laggard, held 1q
    s = np.array(spreads)
    if len(s) < 5:
        return {"n": int(len(s))}
    t_stat = float(s.mean() / (s.std(ddof=1) / np.sqrt(len(s))))
    return {
        "n": int(len(s)),
        "mean_spread": float(s.mean()),
        "hit_rate": float((s > 0).mean()),
        "t_stat": t_stat,
    }


def run() -> dict:
    res = residuals()
    pers = _persistence(res)
    pair = _rank_pair_test(res)
    print("Airline relative-value (share residual vs TSA baseline, ex-COVID)")
    print("=" * 64)
    span = f"{res.index.min()}..{res.index.max()}" if len(res) else "n/a"
    print(f"  carriers: {list(res.columns)}, {len(res)} quarters {span}")
    print(
        f"  latest share residual (most recent q): "
        f"{ {c: round(res[c].dropna().iloc[-1], 3) for c in res.columns} }"
    )
    print(
        f"  lag-1 autocorr (share momentum): {pers['lag1_autocorr']:+.2f}  "
        f"CI[{pers['ci95'][0]:+.2f},{pers['ci95'][1]:+.2f}]  (n={pers['n_pairs']})"
    )
    if "mean_spread" in pair:
        verdict = (
            "persists -> tradeable lead"
            if pair["hit_rate"] > 0.5 and pair["t_stat"] > 1
            else "no usable persistence"
        )
        print(
            f"  rank pair (long gainer/short laggard, next-q spread): "
            f"mean={pair['mean_spread']:+.3f}, hit={pair['hit_rate']:.0%}, "
            f"t={pair['t_stat']:+.2f} (n={pair['n']}) -> {verdict}"
        )
    out = {"persistence": pers, "rank_pair": pair}
    (config.OUTPUT_DIR / "relative_value.json").write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    run()
