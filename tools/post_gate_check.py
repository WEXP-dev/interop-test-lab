#!/usr/bin/env python3
"""Re-verify a frozen staging tree immediately before upload.

The gate froze a manifest. Between that moment and the upload, nothing is
supposed to have happened. This checks that claim rather than trusting the
ordering of the steps that assert it — an added step, a reordered step, or a
process still running in the background all show up here as a mismatch.

    python3 tools/post_gate_check.py --staging build/evidence
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from staging import (  # noqa: E402
    GateFailure, MANIFEST_NAME, load_manifest, sha256_file, walk_staging,
)


def verify(staging: Path) -> dict:
    staging = staging.resolve()
    manifest = load_manifest(staging / MANIFEST_NAME)
    declared = {entry["path"]: entry for entry in manifest["entries"]}
    present = set(walk_staging(staging)) - {MANIFEST_NAME}

    appeared = sorted(present - set(declared))
    vanished = sorted(set(declared) - present)
    if appeared:
        raise GateFailure(f"files appeared after the disclosure gate: {', '.join(appeared)}")
    if vanished:
        raise GateFailure(f"files vanished after the disclosure gate: {', '.join(vanished)}")

    for relative, entry in sorted(declared.items()):
        path = staging / relative
        if path.stat().st_size != entry["bytes"] or sha256_file(path) != entry["sha256"]:
            raise GateFailure(f"file mutated after the disclosure gate: {relative}")

    return {
        "record_kind": "interop-lab-post-gate-check",
        "status": "UNCHANGED",
        "entries_verified": len(declared),
        "non_claims": [
            "UNCHANGED means the staged bytes still match the frozen manifest.",
            "It is not a statement about what those bytes mean.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = verify(args.staging)
    except (GateFailure, OSError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"record_kind": "interop-lab-post-gate-check",
                          "status": "MUTATED", "reason": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
