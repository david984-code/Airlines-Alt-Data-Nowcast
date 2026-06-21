"""Out-of-sample walk-forward test of the TSA -> carrier-RPM nowcast.

In-sample r is necessary but not sufficient. This rolling-origin (expanding
window) test mimics real use: at each quarter t we know only data through t, fit
the seasonal adjustment AND the TSA->RPM regression on the training window, and
nowcast that quarter's reported RPM growth from TSA growth known ~6 weeks earlier.
Scored against a no-skill baseline (predict the training-mean growth).
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

import config

from .analysis import reported_quarterly, tsa_quarterly

_MIN_TRAIN = 10  # quarters before the first nowcast (trend + 3 dummies + slope)


def _deseason_growth(s: pd.Series, train_n: int) -> pd.Series:
    """Deseasonalized QoQ log-growth, seasonal factors fit on the train window."""
    y = np.log(s.to_numpy())
    q = np.array([int(p[-1]) for p in s.index])
    dummies = np.column_stack([(q == k).astype(float) for k in (2, 3, 4)])
    x = np.column_stack([np.ones(train_n), np.arange(train_n), dummies[:train_n]])
    beta, *_ = np.linalg.lstsq(x, y[:train_n], rcond=None)
    return pd.Series(np.diff(y - dummies @ beta[2:]), index=s.index[1:])


def _oos_series(tsa: pd.Series, rpm: pd.Series) -> tuple[np.ndarray, ...]:
    """Point-in-time (pred, actual, baseline) growth per testable quarter."""
    preds, actuals, baselines = [], [], []
    for t in range(_MIN_TRAIN, len(tsa)):
        gs = _deseason_growth(tsa.iloc[: t + 1], t)
        gr = _deseason_growth(rpm.iloc[: t + 1], t)
        train = pd.DataFrame({"s": gs, "r": gr}).iloc[: t - 1].dropna()
        if len(train) < 6 or train["s"].std() == 0:
            continue
        b, a = np.polyfit(train["s"], train["r"], 1)
        preds.append(a + b * gs.iloc[t - 1])
        actuals.append(gr.iloc[t - 1])
        baselines.append(train["r"].mean())
    return np.array(preds), np.array(actuals), np.array(baselines)


def walk_forward(
    carrier: str, metric: str = "revenue_passenger_miles", since: str | None = None
) -> dict:
    tsa = tsa_quarterly()
    rpm = reported_quarterly(metric)[carrier].dropna()
    common = tsa.index.intersection(rpm.index)
    if since:  # restrict the WHOLE series so training is also post-COVID
        common = common[common >= since]
    preds, actuals, baselines = _oos_series(tsa.loc[common], rpm.loc[common])
    if len(preds) < 5:
        return {"carrier": carrier, "since": since, "n_test": int(len(preds))}
    rmse_m = float(np.sqrt(np.mean((actuals - preds) ** 2)))
    rmse_b = float(np.sqrt(np.mean((actuals - baselines) ** 2)))
    return {
        "carrier": carrier,
        "since": since,
        "n_test": int(len(preds)),
        "oos_r": float(np.corrcoef(preds, actuals)[0, 1]),
        "rmse_improvement": float(1 - rmse_m / rmse_b),
        "direction_hit_rate": float(np.mean(np.sign(preds) == np.sign(actuals))),
    }


def _line(r: dict) -> str:
    if "oos_r" not in r:
        return f"  {r['carrier']:6} {str(r['since'] or 'full'):8} insufficient (n={r['n_test']})"
    verdict = "holds" if r["oos_r"] > 0.3 and r["rmse_improvement"] > 0 else "does NOT hold"
    return (
        f"  {r['carrier']:6} {str(r['since'] or 'full'):8} n={r['n_test']:>2}  "
        f"OOS r={r['oos_r']:+.2f}  RMSE {r['rmse_improvement']:+.0%}  "
        f"hit {r['direction_hit_rate']:.0%}  -> {verdict}"
    )


def run(carriers: tuple[str, ...] = ("LUV", "JBLU", "DAL")) -> list[dict]:
    # Full window (training includes COVID) AND ex-COVID (test is normal-times):
    # the contrast exposes carriers whose OOS fit is just COVID-recovery.
    results = [walk_forward(c) for c in carriers]
    results += [walk_forward(c, since="2021Q1") for c in carriers]
    print("TSA -> carrier RPMs — walk-forward (expanding window, no look-ahead)")
    print("=" * 70)
    for r in results:
        print(_line(r))
    (config.OUTPUT_DIR / "walkforward.json").write_text(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    run()
