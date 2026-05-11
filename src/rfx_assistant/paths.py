"""Centralised filesystem paths."""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
FIXTURES = DATA / "fixtures"
PRECOMPUTED = FIXTURES / "precomputed"
SOURCING_LIBRARY = FIXTURES / "sourcing_library"
BIDS_DIR = FIXTURES / "bids"
RUNS = DATA / "runs"
OUTPUTS = ROOT / "outputs"
SCHEMAS = ROOT / "schemas"

for p in (RUNS, OUTPUTS):
    p.mkdir(parents=True, exist_ok=True)
