# Airlines Alt-Data Nowcast (TSA → carrier RPMs)

[![CI](https://github.com/david984-code/Airlines-Alt-Data-Nowcast/actions/workflows/ci.yml/badge.svg)](https://github.com/david984-code/Airlines-Alt-Data-Nowcast/actions/workflows/ci.yml)

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

**The story:** TSA sees US throughput and nowcasts **all the carriers' RPMs**
ex-COVID — strongest for domestic-pure carriers (Southwest, JetBlue), a bit weaker
for Delta, whose ~30% international RPMs TSA can't see and which therefore add
noise (not enough to null it). In-sample ex-COVID, lag 0:

| Carrier | r | 95% CI | n |
|---|---|---|---|
| **JBLU** (domestic-heavy) | +0.97 | [+0.88, +0.99] | 20 |
| **LUV** (Southwest, ~100% domestic) | +0.96 | [+0.85, +0.98] | 20 |
| DAL (Delta, ~30% intl) | +0.92 | [+0.78, +0.97] | 16 |
| Industry aggregate (core 4) | +0.97 | [+0.90, +0.99] | 16 |

> **Honest-numbers note (a bug we caught):** an earlier version reported Delta as
> a *null* and called it "international dilution." That was a **data error** — the
> exhibit picker was grabbing Delta's earnings *presentation deck* instead of the
> press release, corrupting its RPM series. After fixing the picker (`_press_release_url`),
> Delta holds. The dilution effect is real but *partial* (Delta is the weakest
> leg), not a kill. Re-running after the data fix overturned the wrong conclusion.

### Out-of-sample confirmation (`src/walkforward.py`)

Rolling-origin, expanding window, no look-ahead (deseasonalization *and* the
TSA→RPM regression re-fit on the training window each step), full-window and
ex-COVID:

| Carrier | OOS r (full) | OOS r (ex-COVID) | ex-COVID hit | verdict |
|---|---|---|---|---|
| **LUV** | +0.98 | **+0.93** | 82% | holds |
| **JBLU** | +0.98 | **+0.97** | 100% | holds |
| DAL | +1.00 | +0.49 (n=7) | 57% | holds, weakest |

LUV/JBLU hold strongly under every cut. Delta holds too but is the weakest leg
(ex-COVID OOS r=+0.49 on only 7 quarters) — consistent with international RPMs
adding TSA-invisible noise.

### Relative-value / share signal (`src/relative_value.py`) — honest null

A carrier's RPM growth minus its TSA-implied baseline is its idiosyncratic
*share* move. The pair thesis (long the share-gainer, short the laggard) needs the
residual to **persist**. It doesn't: pooled lag-1 autocorrelation is **−0.52**
(CI [−0.71, −0.29]) — share **mean-reverts**, so a momentum pair *loses*
(next-quarter spread t=−4.26, 10% hit). The sign says a *contrarian* pair is the
right direction, but only LUV+JBLU clear the data threshold — far too thin to
claim. **Verdict: traffic share is mean-reverting, not trending; a real
cross-sectional pair needs more domestic carriers** (recover AAL/UAL/ALK) and a
link to relative *stock* returns. The nowcast legs (LUV, JBLU) stand on their own.

## What's built

```
config.py                  # carriers -> CIK, paths, START_DATE
src/data/tsa.py            # TSA daily throughput (2,728 days, 2019-2026)
src/data/kpi_edgar.py      # carrier traffic KPIs from EDGAR + triangulation verify
src/data/cache.py, net.py  # CSV cache + retry/backoff
src/analysis.py            # TSA quarterly, carrier/industry quarterly
src/nowcast.py             # deseasonalized-growth bridge + block-bootstrap CI
src/walkforward.py         # rolling-origin OOS validation (no look-ahead)
src/relative_value.py      # carrier-vs-TSA share residual + persistence test
data/kpi_ground_truth.csv  # 1,187 verified rows (RPM/ASM/load factor/enplaned)
```

KPI RPM coverage (all current): LUV 2005Q2→, JBLU 2003Q3→, DAL 2006Q1→,
AAL 2013Q2→. UAL stops 2022Q4 and ALK reports RPMs under a non-matching label —
both fixable label issues, a known next step.

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
3. ✅ Walk-forward OOS (`walkforward.py`): LUV r=+0.93, JBLU r=+0.97 ex-COVID
      hold; DAL holds but weakest (OOS +0.49, n=7).
4. ✅ Relative-value share signal (`relative_value.py`): residuals **mean-revert**
      (autocorr −0.52) — momentum pair fails; needs more carriers + stock-return
      link before a contrarian pair is claimable.
5. ✅ Fixed exhibit picker (was grabbing presentation decks) → recovered AAL to
      2026Q1 and **corrected Delta** (the earlier DAL "null" was that data bug).
      ⬜ Still: UAL post-2022 + ALK RPM label.
6. ✅ Quality gate (ruff + mypy + pytest, uv.lock, CI) mirroring the gig reader.
      ⬜ Still: load-factor / enplaned-passengers as alternative targets.

## Part of a series

A free-data **consumer subsector reader** built to a consistent honest-numbers bar
(validated signals + openly-reported nulls + a ruff/mypy/pytest CI gate):

- **Airlines (this repo)** — TSA throughput → carrier RPM growth (OOS r≈0.93–0.97).
- [Consumer-Gig-Nowcast](https://github.com/david984-code/Consumer-Gig-Nowcast)
  — NYC TLC trips → Uber Mobility GB growth (OOS r≈0.98).
- [Hospitality-Alt-Data-Dashboard](https://github.com/david984-code/hospitality-alt-data-dashboard)
  — TSA / BLS / Trends → hotel-franchisor demand (MAR/HLT/H).

Recurring finding across both: free alt-data excels at *nowcasting the print* as a
conviction input, while systematic tradeable pairs keep coming up empty — reported
honestly rather than dressed up.
