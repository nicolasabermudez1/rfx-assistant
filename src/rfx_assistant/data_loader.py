"""Load mock fixtures from disk. Cached for the Streamlit lifetime."""
from __future__ import annotations
import json
from pathlib import Path
from functools import lru_cache

import yaml

from rfx_assistant.paths import FIXTURES, PRECOMPUTED, SOURCING_LIBRARY, BIDS_DIR


@lru_cache(maxsize=1)
def category_strategy() -> str:
    p = FIXTURES / "category_strategy_data_centre_cooling.md"
    return p.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def sourcing_library() -> dict:
    libs = {}
    for f in sorted(SOURCING_LIBRARY.glob("*.yml")):
        libs[f.stem] = yaml.safe_load(f.read_text(encoding="utf-8"))
    return libs


@lru_cache(maxsize=1)
def scoring_framework() -> dict:
    return yaml.safe_load((FIXTURES / "scoring_framework.yml").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def boilerplate_terms() -> str:
    return (FIXTURES / "boilerplate_terms.md").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def suppliers() -> list[dict]:
    return json.loads((PRECOMPUTED / "suppliers.json").read_text(encoding="utf-8"))["suppliers"]


@lru_cache(maxsize=1)
def bid_extractions() -> list[dict]:
    return json.loads((PRECOMPUTED / "bid_extractions.json").read_text(encoding="utf-8"))["extractions"]


@lru_cache(maxsize=1)
def scores() -> dict:
    return json.loads((PRECOMPUTED / "scores.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def shortlist() -> dict:
    return json.loads((PRECOMPUTED / "shortlist.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def sorry_thanks() -> dict:
    return json.loads((PRECOMPUTED / "sorry_thanks.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def spec_workspace() -> dict:
    return json.loads((PRECOMPUTED / "spec_workspace.json").read_text(encoding="utf-8"))


def bid_files() -> list[Path]:
    return sorted([p for p in BIDS_DIR.iterdir() if p.is_file()])


def supplier_by_id(supplier_id: str) -> dict:
    for s in suppliers():
        if s["id"] == supplier_id:
            return s
    raise KeyError(supplier_id)


def extraction_by_id(supplier_id: str) -> dict:
    for e in bid_extractions():
        if e["supplier_id"] == supplier_id:
            return e
    raise KeyError(supplier_id)


def validate_all() -> list[str]:
    """Run a startup validation across all fixtures. Returns a list of human-readable errors."""
    errors: list[str] = []
    try:
        assert category_strategy(), "category strategy empty"
        assert sourcing_library(), "sourcing library empty"
        assert scoring_framework(), "scoring framework empty"
        assert boilerplate_terms(), "boilerplate terms empty"
        assert len(suppliers()) == 3, f"expected 3 suppliers, got {len(suppliers())}"
        assert len(bid_extractions()) == 3, "expected 3 bid extractions"
        assert shortlist()["ranking"], "shortlist ranking empty"
        assert len(bid_files()) >= 3, "expected at least 3 bid files in fixtures/bids"
    except AssertionError as e:
        errors.append(str(e))
    except Exception as e:
        errors.append(f"unexpected fixture error: {e}")
    return errors
