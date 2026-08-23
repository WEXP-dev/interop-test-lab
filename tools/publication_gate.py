#!/usr/bin/env python3
"""Freeze a staged publication tree against an exact allowlist and manifest.

The gate answers one question: *may these exact bytes leave the run?* It is
deliberately not a scanner. A scanner asks whether it recognises anything bad;
this asks whether every file present was admitted in advance, by path, in
writing. An unknown file is not "probably fine" — it is a failure.

Order matters, and the order is fixed by the caller: all semantic execution
finishes, the tree is staged, then this runs, then the deny scan runs, then
nothing mutating happens again. This program never writes into the staging tree
except to place the manifest it just computed.

    python3 tools/publication_gate.py --staging build/evidence \
        --allowlist publication/ALLOWLIST.json \
        --experiment-id X-001 --report build/gate.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from staging import (  # noqa: E402
    GateFailure, MANIFEST_NAME, build_manifest, walk_staging, write_manifest,
)


def admitted_paths(allowlist: dict) -> set[str]:
    admitted = allowlist.get("admitted")
    if not isinstance(admitted, list) or not admitted:
        raise GateFailure("allowlist admits nothing; refusing to publish")
    paths: set[str] = set()
    for entry in admitted:
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            raise GateFailure("allowlist entry has no path")
        if path.startswith("/") or ".." in Path(path).parts:
            raise GateFailure(f"allowlist path is not a safe relative path: {path}")
        if "*" in path or "?" in path:
            # A wildcard is how an unrevealed blind fixture reaches a bundle
            # nobody meant to put it in.
            raise GateFailure(f"allowlist paths are exact; wildcards are refused: {path}")
        if path in paths:
            raise GateFailure(f"duplicate allowlist path: {path}")
        paths.add(path)
    return paths


def gate(staging: Path, allowlist: dict, *, experiment_id: str) -> dict:
    staging = staging.resolve()
    admitted = admitted_paths(allowlist)
    present = set(walk_staging(staging))

    undeclared = sorted(present - admitted)
    missing = sorted(admitted - present - {MANIFEST_NAME})

    if undeclared:
        raise GateFailure(
            "staging tree carries files no allowlist entry admits: "
            + ", ".join(undeclared)
        )
    if missing:
        # Absent evidence is a legitimate state — a party may not have run — so
        # this is reported, not fatal. What is fatal is a file nobody admitted.
        pass

    manifest = build_manifest(staging, experiment_id=experiment_id)
    write_manifest(staging, manifest)

    return {
        "record_kind": "interop-lab-publication-gate",
        "status": "ADMITTED",
        "experiment_id": experiment_id,
        "admitted_entries": manifest["entry_count"],
        "declared_but_absent": missing,
        "manifest": MANIFEST_NAME,
        "non_claims": [
            "ADMITTED means every staged file was named in the allowlist in advance.",
            "It is not a statement about what the files mean.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--allowlist", type=Path, required=True)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    try:
        allowlist = json.loads(args.allowlist.read_text(encoding="utf-8"))
        report = gate(args.staging, allowlist, experiment_id=args.experiment_id)
    except (GateFailure, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"record_kind": "interop-lab-publication-gate",
                          "status": "REFUSED", "reason": str(exc)}, sort_keys=True))
        return 1

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
