"""Reported carrier traffic KPIs from SEC EDGAR earnings press releases.

Targets for the TSA nowcast: Revenue Passenger Miles (RPMs), Available Seat Miles
(ASMs), Load Factor, and (where reported) Enplaned Passengers. Airline tables
print ``[current, year-ago, % change]``; we extract the two quarter columns and
verify every value by cross-release triangulation (a quarter is trusted when >=2
releases agree, then the rest of a proven release is trusted too).
"""

from __future__ import annotations

import json
import math
import re
from io import StringIO

import pandas as pd
import requests

import config

from .net import network_retry

_UA = {"User-Agent": config.SEC_UA}
_A = "https://www.sec.gov/Archives/edgar/data"
_SUB = "https://data.sec.gov/submissions"
_RELEASE_CACHE = "edgar_releases.json"

# Filing month -> (fiscal quarter, year offset): Q4 in Jan-Feb, Q1 Apr-May, etc.
_MONTH_TO_Q = {
    1: ("Q4", -1),
    2: ("Q4", -1),
    3: ("Q4", -1),
    4: ("Q1", 0),
    5: ("Q1", 0),
    6: ("Q1", 0),
    7: ("Q2", 0),
    8: ("Q2", 0),
    9: ("Q2", 0),
    10: ("Q3", 0),
    11: ("Q3", 0),
    12: ("Q3", 0),
}

# Anchored regex (label must START with these) -> canonical metric. Anchoring
# avoids matching derived rows like "Passenger revenue per available seat mile".
AIRLINE_METRICS = [
    ("revenue_passenger_miles", re.compile(r"^revenue passenger miles")),
    ("available_seat_miles", re.compile(r"^available seat miles")),
    ("enplaned_passengers", re.compile(r"^enplaned passengers")),
    ("load_factor", re.compile(r"^(passenger )?load factor")),
]
_UNITS = {
    "revenue_passenger_miles": "millions",
    "available_seat_miles": "millions",
    "enplaned_passengers": "thousands",
    "load_factor": "percent",
}


@network_retry
def _get(url: str) -> requests.Response:
    r = requests.get(url, headers=_UA, timeout=30)
    r.raise_for_status()
    return r


def _earnings_8ks(cik: int) -> list[tuple[str, str, str]]:
    """All earnings 8-Ks (item 2.02) as (filing_date, accession, cover_doc)."""
    j = _get(f"{_SUB}/CIK{cik:010d}.json").json()
    blocks = [j["filings"]["recent"]]
    for f in j["filings"].get("files", []):
        blocks.append(_get(f"{_SUB}/{f['name']}").json())
    out = []
    for b in blocks:
        for form, date, items, acc, doc in zip(
            b["form"],
            b["filingDate"],
            b["items"],
            b["accessionNumber"],
            b["primaryDocument"],
            strict=True,
        ):
            if form == "8-K" and "2.02" in items:
                out.append((date, acc.replace("-", ""), doc))
    return out


def _period_from_date(filing_date: str) -> str:
    y, m = int(filing_date[:4]), int(filing_date[5:7])
    q, off = _MONTH_TO_Q[m]
    return f"{y + off}{q}"


def _press_release_url(cik: int, acc: str, cover_doc: str) -> str | None:
    """The press-release exhibit = largest .htm that isn't the cover or XBRL."""
    idx = _get(f"{_A}/{cik}/{acc}/index.json").json()["directory"]["item"]
    best, best_size = None, -1
    for it in idx:
        low = it["name"].lower()
        if not low.endswith(".htm") or low.startswith("r") or it["name"] == cover_doc:
            continue
        if "8-k" in low or "8k" in low or "form8" in low:
            continue
        if (size := int(it.get("size", 0))) > best_size:
            best, best_size = it["name"], size
    return f"{_A}/{cik}/{acc}/{best}" if best else None


def discover(ticker: str, refresh: bool = False) -> dict[str, str]:
    """Map period -> press-release URL for a carrier, cached to data/."""
    cache_path = config.DATA_DIR / _RELEASE_CACHE
    cached = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    if not refresh and ticker in cached:
        return cached[ticker]
    cik = config.CARRIERS[ticker]
    releases: dict[str, str] = {}
    for date, acc, doc in _earnings_8ks(cik):
        period = _period_from_date(date)
        if period in releases:  # keep the earliest-filed (original) release
            continue
        if url := _press_release_url(cik, acc, doc):
            releases[period] = url
    cached[ticker] = dict(sorted(releases.items()))
    cache_path.write_text(json.dumps(cached, indent=2))
    return cached[ticker]


def _num(tok: str) -> float | None:
    tok = tok.replace(",", "").replace("$", "").strip()
    neg = tok.startswith("(") and tok.endswith(")")
    tok = tok.strip("()%")
    try:
        v = float(tok)
    except ValueError:
        return None
    return -v if neg and math.isfinite(v) else (v if math.isfinite(v) else None)


def _ordered_distinct(vals: list[float]) -> list[float]:
    """Collapse consecutive colspan-duplicated values, preserving column order."""
    out: list[float] = []
    for v in vals:
        if not out or out[-1] != v:
            out.append(v)
    return out


def _match_metric(label: str) -> str | None:
    label = re.sub(r"\s+", " ", label).strip().lower()
    for metric, pat in AIRLINE_METRICS:
        if pat.match(label):
            return metric
    return None


def _read_tables(html: str) -> list[pd.DataFrame]:
    """Parse HTML tables, tolerating malformed filings (lxml -> bs4 -> skip)."""
    for flavor in ("lxml", "bs4"):
        try:
            return pd.read_html(StringIO(html), flavor=flavor)
        except (ImportError, ValueError):
            continue
    return []


def _extract_airline(url: str) -> dict[str, tuple[float, float]]:
    """Return {metric: (current, year_ago)} from a carrier press release."""
    found: dict[str, tuple[float, float]] = {}
    for tbl in _read_tables(_get(url).text):
        for _, row in tbl.iterrows():
            cells = [str(c) for c in row.values if str(c) != "nan"]
            if not cells:
                continue
            metric = _match_metric(cells[0])
            if not metric or metric in found:
                continue
            nums = [v for c in cells[1:] if (v := _num(c)) is not None and abs(v) >= 1]
            distinct = _ordered_distinct(nums)  # collapse colspan duplicates
            if len(distinct) >= 2:  # [current, year-ago, %change...]
                found[metric] = (distinct[0], distinct[1])
    return found


def _prior_period(period: str) -> str:
    y, q = int(period[:4]), int(period[-1])
    return f"{y - 1}Q{q}"


def _close(a: float, b: float) -> bool:
    return abs(a - b) < max(0.1, 0.005 * abs(a))


_Obs = dict[tuple[str, str], list[tuple[float, str]]]


def _push(obs: _Obs, period: str, metric: str, value: float, url: str) -> None:
    obs.setdefault((period, metric), []).append((value, url))


def _consensus(vals: list[tuple[float, str]]) -> tuple[float, int]:
    """Value backed by the most distinct releases, and that release count."""
    best, best_n = vals[0][0], 0
    for v, _ in vals:
        n = len({u for v2, u in vals if _close(v, v2)})
        if n > best_n:
            best, best_n = v, n
    return best, best_n


def _anchors_and_trusted(obs: _Obs) -> tuple[dict[tuple[str, str], float], set[str]]:
    anchor: dict[tuple[str, str], float] = {}
    for key, vals in obs.items():
        val, n = _consensus(vals)
        if n >= 2:
            anchor[key] = val
    trusted = {u for key, val in anchor.items() for v, u in obs[key] if _close(v, val)}
    return anchor, trusted


def _triangulate(obs: _Obs, ticker: str) -> list[dict]:
    """Anchor/trust/verify pooled observations. Pure -> unit-tested directly."""
    anchor, trusted = _anchors_and_trusted(obs)
    rows = []
    for (period, metric), vals in obs.items():
        val, _ = _consensus(vals)
        src = next((u for v, u in vals if _close(v, val)), vals[0][1])
        verified = (period, metric) in anchor or any(
            u in trusted and _close(v, val) for v, u in vals
        )
        rows.append(
            {
                "ticker": ticker,
                "period": period,
                "metric": metric,
                "value": val,
                "source_url": src,
                "verified": verified,
            }
        )
    return rows


def fetch(ticker: str) -> pd.DataFrame:
    """Verified quarterly traffic KPIs for one carrier."""
    releases = discover(ticker)
    obs: _Obs = {}
    for period, url in releases.items():
        for metric, (cur, ya) in _extract_airline(url).items():
            _push(obs, period, metric, cur, url)
            _push(obs, _prior_period(period), metric, ya, url)
    rows = _triangulate(obs, ticker)
    return pd.DataFrame(rows).sort_values(["metric", "period"]).reset_index(drop=True)


def build() -> pd.DataFrame:
    """Fetch all carriers; write only cross-check-verified rows to the CSV."""
    raw = pd.concat([fetch(t) for t in config.CARRIERS], ignore_index=True)
    dropped = raw[~raw["verified"]]
    if not dropped.empty:
        print(f"Dropped {len(dropped)} unverified rows (no corroborating release).")
    df = raw[raw["verified"]].copy()
    df["unit"] = df["metric"].map(_UNITS)
    df = df[["ticker", "period", "metric", "value", "unit", "source_url", "verified"]]
    out = config.DATA_DIR / "kpi_ground_truth.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {out}  ({len(df)} verified rows)")
    print(df.groupby("ticker")["period"].agg(["min", "max", "count"]).to_string())
    return df


if __name__ == "__main__":
    build()
