"""Runtime configuration for the Airlines Alt-Data Nowcast.

Thesis: TSA daily checkpoint throughput (near-ground-truth for US air travel) is
a pre-earnings nowcast of carriers' reported traffic (RPMs / enplaned
passengers). TSA is industry-wide, so it predicts the *industry baseline*; each
carrier's growth minus the TSA-implied baseline is a relative-value (share)
signal -- the within-subsector pair for the Consumer L/S book.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    _ENV = Path(__file__).resolve().parent / ".env"
    if _ENV.exists():
        load_dotenv(_ENV)
except ImportError:
    pass

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "outputs"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

CACHE_TTL_HOURS = 24.0
START_DATE = "2019-01-01"  # TSA passenger-volumes coverage begins 2019

# Carriers we cover -> SEC CIK. Southwest is ~100% domestic (cleanest TSA bridge);
# the legacy majors carry an international mix that TSA can't see.
CARRIERS: dict[str, int] = {
    "LUV": 92380,  # Southwest (pure domestic)
    "DAL": 27904,  # Delta
    "UAL": 100517,  # United Airlines Holdings
    "AAL": 6201,  # American Airlines Group
    "ALK": 766421,  # Alaska Air Group
    "JBLU": 1158463,  # JetBlue
}

SEC_UA = os.environ.get("SEC_UA", "David Shaltakoff research dns817@gmail.com")
