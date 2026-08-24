#!/usr/bin/env python3
"""Synthetic pilot counterparty. Public, non-sensitive, no WEXP or EMILIA semantics.

Runs in the counterparty domain with no credential and no WEXP checkout. It reads
its own declared cases and writes its own native result. Nothing here knows what
WEXP is, which is the point: a counterparty should not have to.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    out = pathlib.Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else ROOT / "RESULTS.json"
    cases = sorted((ROOT / "cases").glob("*.json"))
    results = {}
    for path in cases:
        case = json.loads(path.read_text(encoding="utf-8"))
        # The synthetic party's entire "semantics": it observes its own case id.
        results[case["case_id"]] = {"synthetic_result": "OK", "observed_case_id": case["case_id"]}
    payload = {
        "record_kind": "synthetic-pilot-native-result",
        "party": "SYNTHETIC-PILOT-PARTY",
        "results": results,
        "non_claims": [
            "Synthetic. This is not a protocol, not an interoperability claim, and not a WEXP or EMILIA result.",
        ],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"synthetic pilot party wrote {len(results)} result(s) to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
