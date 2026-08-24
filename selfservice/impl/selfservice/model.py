"""Shared primitives. Deliberately stdlib-only so the validator can run anywhere."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

REQUEST_SCHEMA_ID = "https://wexp.dev/schemas/interop-request-v0.2.json"

#: Outcomes the validator may report. A validator that invents a state outside
#: this set has left the contract.
OUTCOMES = (
    "VALIDATED",
    "VALIDATION_FAILED",
    "REQUIRES_DESIGN_REVIEW",
    "REQUIRES_DISCLOSURE_REVIEW",
    "BLOCKED_BY_GENERIC_CAPABILITY_GAP",
)

CHARTER_INVARIANTS = ("I-01", "I-02", "I-03a", "I-03b", "I-04", "I-05")


class Refused(ValueError):
    """A step failed closed. The message names what was refused, never the bytes."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    """The digest encoding used for receipts, tickets and the ledger."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8") + b"\n"


def canonical_sha256(value) -> str:
    return sha256_bytes(canonical(value))


def load_exact(path: Path) -> tuple[bytes, dict]:
    """Read once. The digest and the parsed value describe the same bytes.

    Hashing a path and separately parsing it cannot be shown to describe the
    same content: anything rewriting the path between the two makes the recorded
    digest attest to bytes that were never evaluated.
    """
    if path.is_symlink() or not path.is_file():
        raise Refused(f"not a regular non-symlink file: {path.name}")
    raw = path.read_bytes()
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Refused(f"{path.name} is not readable UTF-8 JSON: {exc}") from exc
    return raw, parsed


@dataclass
class Result:
    outcome: str
    diagnostics: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.outcome == "VALIDATED"
