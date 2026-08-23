#!/usr/bin/env python3
"""Accept a party domain's native output as data, and check that it is what ran.

The coordination domain never executes a counterparty's code. It receives an
artifact. That makes the artifact untrusted input, so it is validated the way
untrusted input is validated: an exact file set, a declared record shape, and
nothing admitted that was not asked for.

The second half is the one that matters for truth in the evidence. The
framework produced its own record of what the counterparty returned, from a
copy of the counterparty it holds itself. This compares that record, case by
case, against what the counterparty's *own repository* actually produced in its
own domain. A disagreement means the published evidence would describe a run
that did not happen, so it is refused — and refused as an infrastructure or
authority finding, never as a result about either party.

    python3 tools/ingest_native.py \
        --native build/incoming/counterparty-native \
        --bundle build/run/semantic-bundle.json \
        --party-id GLYPHLOCK \
        --expected-commit 8753d05f... \
        --output build/evidence/native/glyphlock
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from staging import GateFailure, canonical_sha256  # noqa: E402

EXPECTED_FILES = {"RESULTS.json", "PARTY-DOMAIN.json"}
MAX_ARTIFACT_BYTES = 4 * 1024 * 1024


def load_incoming(native: Path) -> tuple[dict, dict]:
    native = native.resolve()
    if not native.is_dir():
        raise GateFailure(f"no party-domain artifact at {native}")

    present = set()
    for path in sorted(native.rglob("*")):
        if path.is_symlink():
            raise GateFailure(f"symlink in party-domain artifact: {path.name}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise GateFailure(f"special entry in party-domain artifact: {path.name}")
        relative = path.relative_to(native).as_posix()
        if relative not in EXPECTED_FILES:
            raise GateFailure(f"party-domain artifact carries an undeclared file: {relative}")
        if path.stat().st_size > MAX_ARTIFACT_BYTES:
            raise GateFailure(f"party-domain artifact is implausibly large: {relative}")
        present.add(relative)

    missing = sorted(EXPECTED_FILES - present)
    if missing:
        raise GateFailure(f"party-domain artifact is incomplete: {', '.join(missing)}")

    try:
        results = json.loads((native / "RESULTS.json").read_text(encoding="utf-8"))
        domain = json.loads((native / "PARTY-DOMAIN.json").read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateFailure(f"party-domain artifact is not readable JSON: {exc}") from exc

    if results.get("record_kind") != "interop-lab-native-results":
        raise GateFailure("party-domain results have the wrong record_kind")
    if domain.get("record_kind") != "interop-lab-party-domain":
        raise GateFailure("party-domain descriptor has the wrong record_kind")
    return results, domain


def cross_check(results: dict, bundle: dict, *, party_id: str) -> dict:
    recorded = bundle.get("native_result_identities", {}).get(party_id)
    if not isinstance(recorded, dict) or not recorded:
        raise GateFailure(f"the run recorded no native result identities for {party_id}")

    observed = {
        entry["case_id"]: canonical_sha256(entry.get("native_result"))
        for entry in results.get("results", [])
    }

    only_in_run = sorted(set(recorded) - set(observed))
    only_in_domain = sorted(set(observed) - set(recorded))
    if only_in_run or only_in_domain:
        raise GateFailure(
            "the party domain and the run disagree about which cases were executed: "
            f"run-only={only_in_run} domain-only={only_in_domain}"
        )

    divergent = sorted(case for case, digest in recorded.items() if observed[case] != digest)
    if divergent:
        raise GateFailure(
            "the counterparty repository's own results differ from the results this "
            f"run recorded for it, on: {', '.join(divergent)}. No semantic conclusion "
            "may be drawn; repin or investigate the counterparty."
        )

    return {
        "record_kind": "interop-lab-party-domain-crosscheck",
        "party_id": party_id,
        "status": "AGREES",
        "cases_checked": len(recorded),
        "non_claims": [
            "AGREES means the counterparty's own domain produced the same native "
            "results this run recorded for it.",
            "It says nothing about whether those results are correct.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--party-id", required=True)
    parser.add_argument("--expected-commit", default="")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        results, domain = load_incoming(args.native)
        if args.expected_commit and domain.get("source_commit") != args.expected_commit:
            raise GateFailure(
                "the party domain reports a source commit that is not the declared pin"
            )
        if results.get("party_id") != args.party_id:
            raise GateFailure("the party-domain artifact is for a different party")
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
        report = cross_check(results, bundle, party_id=args.party_id)
    except (GateFailure, OSError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"record_kind": "interop-lab-party-domain-crosscheck",
                          "status": "REFUSED", "reason": str(exc),
                          "is_experiment_failure": False,
                          "is_portability_failure": False}, sort_keys=True))
        return 1

    args.output.mkdir(parents=True, exist_ok=True)
    for name in sorted(EXPECTED_FILES):
        shutil.copyfile(args.native / name, args.output / name)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
