"""Unit tests for the carrier-KPI extraction/verification logic (no network)."""

from src.data import kpi_edgar as k


def test_num_parses_money_commas_parens_percent():
    assert k._num("56,470") == 56470.0
    assert k._num("(7.4)") == -7.4
    assert k._num("81.6") == 81.6
    assert k._num("nan") is None
    assert k._num("%") is None


def test_ordered_distinct_collapses_colspan_duplicates():
    # The Southwest bug: [current, current, year-ago, year-ago, %change].
    assert k._ordered_distinct([30629.0, 30629.0, 33087.0, 33087.0, -7.4]) == [
        30629.0,
        33087.0,
        -7.4,
    ]


def test_match_metric_is_anchored():
    assert k._match_metric("Revenue passenger miles (RPMs) (in millions)") == (
        "revenue_passenger_miles"
    )
    assert k._match_metric("Available seat miles (millions)") == "available_seat_miles"
    assert k._match_metric("Passenger load factor") == "load_factor"
    # Anchoring must NOT match a derived per-ASM row.
    assert k._match_metric("Passenger revenue per available seat mile (cents)") is None


def test_period_from_filing_month():
    assert k._period_from_date("2026-04-08") == "2026Q1"  # Apr -> Q1
    assert k._period_from_date("2026-01-13") == "2025Q4"  # Jan -> prior Q4
    assert k._period_from_date("2025-07-10") == "2025Q2"
    assert k._period_from_date("2025-10-15") == "2025Q3"


def test_prior_period():
    assert k._prior_period("2026Q1") == "2025Q1"


def test_triangulate_anchors_and_outvotes_garbage():
    obs = {
        ("2025Q1", "rpm"): [(30629.0, "rA"), (30629.0, "rB")],  # 2 agree -> anchor
        ("2025Q2", "rpm"): [(36885.0, "rB")],  # rB trusted -> verified
        ("2024Q4", "rpm"): [(99999.0, "rX"), (34471.0, "rB"), (34471.0, "rC")],  # garbage
        ("2099Q1", "rpm"): [(1.0, "rZ")],  # untrusted single obs
    }
    rows = {r["period"]: r for r in k._triangulate(obs, "LUV")}
    assert rows["2025Q1"]["value"] == 30629.0 and rows["2025Q1"]["verified"]
    assert rows["2025Q2"]["value"] == 36885.0 and rows["2025Q2"]["verified"]
    assert rows["2024Q4"]["value"] == 34471.0 and rows["2024Q4"]["verified"]  # not 99999
    assert rows["2099Q1"]["value"] == 1.0 and not rows["2099Q1"]["verified"]
