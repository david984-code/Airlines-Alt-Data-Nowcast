# Airlines Alt-Data Nowcast (TSA → carrier RPMs)

A consumer-sector **subsector reader** for the Consumer L/S book: nowcast US
airlines' reported traffic (Revenue Passenger Miles) from **TSA daily checkpoint
throughput** — near-ground-truth for US air travel, available ~6 weeks before
carriers print. Sibling to the rideshare/gig and lodging readers; same
honest-numbers methodology (deseasonalized growth, block-bootstrap CIs, ex-COVID
robustness, lag-0 contemporaneous headline).

## The finding (first pass, in-sample, ex-COVID, lag 0)

| Bridge (deseasonalized QoQ growth) | r | 95% CI | n | verdict |
|---|---|---|---|---|
| **TSA → LUV (Southwest) RPMs** | **+0.96** | [+0.85, +0.98] | 20 | **signal ✓** |
| **TSA → JBLU (JetBlue) RPMs** | **+0.97** | [+0.88, +0.99] | 20 | **signal ✓** |
| TSA → DAL (Delta) RPMs | −0.01 | [−0.22, +0.48] | 18 | no signal |
| TSA → industry RPMs (core 4) | +0.27 | [+0.02, +0.72] | 18 | weak |

**The story — and the analog to the gig reader:** TSA only sees *US* throughput,
so it nowcasts **domestic-heavy carriers** strongly (Southwest ~100% domestic,
JetBlue mostly domestic) but **fails for international-mix carriers** (Delta ~30%+
international RPMs that TSA can't observe). That's the same shape as
NYC-trips → Uber *Mobility* (works) vs *total* trips diluted by Eats (fails):
match the signal's coverage to the metric's coverage.

> Two defended legs (LUV, JBLU) and a clean relative-value hook: a domestic
> carrier's RPM growth *minus* the TSA-implied baseline is a share signal.

## What's built

```
config.py                  # carriers -> CIK, paths, START_DATE
src/data/tsa.py            # TSA daily throughput (2,728 days, 2019-2026)
src/data/kpi_edgar.py      # carrier traffic KPIs from EDGAR + triangulation verify
src/data/cache.py, net.py  # CSV cache + retry/backoff
src/analysis.py            # TSA quarterly, carrier/industry quarterly
src/nowcast.py             # deseasonalized-growth bridge + block-bootstrap CI
data/kpi_ground_truth.csv  # 930 verified rows (RPM/ASM/load factor/enplaned)
```

KPI coverage: LUV 2005Q2→2026Q1, JBLU 2003Q3→2026Q1, ALK 2003Q4→2026Q1,
DAL 2018Q1→2026Q1 (all current). AAL stops 2017Q2 and UAL 2022Q4 — their press
releases changed format; recovering them is a known next step.

## Run

```bash
uv sync   # or: pip install -r requirements.txt
uv run python -m src.data.tsa          # fetch TSA throughput
uv run python -m src.data.kpi_edgar    # build verified carrier KPIs (EDGAR)
uv run python -m src.nowcast           # TSA -> RPM bridge tests
```

## Roadmap

1. ✅ TSA fetcher + carrier KPI extraction (triangulation-verified) + bridge.
2. ✅ **Signal found:** TSA → domestic-carrier RPMs (LUV r=0.96, JBLU r=0.97).
3. ⬜ Walk-forward / rolling-origin OOS validation (no look-ahead), like the gig
      reader — to confirm the in-sample r holds before it sizes anything.
4. ⬜ **Relative-value signal:** carrier RPM growth − TSA-implied baseline → the
      within-subsector pair (long the share-gainer, short the laggard).
5. ⬜ Recover AAL (post-2017) and UAL (post-2022) press-release formats.
6. ⬜ Test load-factor / enplaned-passengers as alternative targets; quality gate
      (ruff + mypy + pytest), uv.lock, CI — mirror the gig reader.
