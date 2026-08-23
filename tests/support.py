"""Shared scaffolding for the lab's own regression tests."""

from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "tools"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

#: The prefix is committed; the value never is. A sentinel with a fixed value in
#: a public repository is a string, not a boundary test.
SENTINEL_PREFIX = "WEXP_PRIVATE_BOUNDARY_SENTINEL"


def new_sentinel() -> str:
    """A fresh sentinel value, generated per test run and never written here."""
    return f"{SENTINEL_PREFIX}_{secrets.token_hex(16)}"


def write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def minimal_allowlist(paths: list[str], *, exceptions: list[dict] | None = None) -> dict:
    return {
        "record_kind": "interop-lab-publication-allowlist",
        "experiment_id": "T-000",
        "admitted": [{"path": path, "artifact_class": "test", "why": "test"}
                     for path in paths],
        "denied_classes": [],
        "strategic_review_exceptions": exceptions or [],
    }
