#!/usr/bin/env python3
"""Run the counterparty in its own execution domain and emit its native result.

This program is the counterparty's side of the exercise and nothing else. It
renders each frozen case into the counterparty's own wire format, invokes the
counterparty's own runner, and writes down exactly what came back. It performs
no comparison, consults no expectation, and holds no WEXP material: a result in
the counterparty's vocabulary leaves here in the counterparty's vocabulary.

It is meant to run in a job that has no secrets, no private checkout and no
publication staging tree. That is the whole point — the code it executes is
controlled by whoever controls the counterparty repository, so it must run
somewhere that losing entirely would cost nothing but the run.

    python3 tools/party_counterparty.py \
        --cases experiments/X-001/cases.json \
        --runner subject/glyphlock/runner.py \
        --workspace build/party/work \
        --output build/party/native
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

WIRE_FORMAT_PREFIX = "GLYPHLOCK/"
RESULT_PREFIX = "GLYPHLOCK-RESULT/"

#: The counterparty's declared field order. Its wire format is line-oriented and
#: order-bearing, so this is transcription, not interpretation.
WIRE_FIELDS = ("warden", "ward-depth", "sigil", "chain", "epoch-band", "attest")

#: The counterparty's exit codes, mapped onto *infrastructure* status only.
#: Nothing here touches what a seal state means.
EXIT_STATUS = {0: "OK", 3: "NOT_IMPLEMENTED", 4: "NOT_CONSTRUCTIBLE"}

#: A counterparty that has not returned within this is an infrastructure fact,
#: not a result about anybody's protocol.
TIMEOUT_SECONDS = 60


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ward_request(case: dict) -> str | None:
    for item in case.get("inputs", []):
        if str(item.get("format", "")).startswith(WIRE_FORMAT_PREFIX):
            lines = [item["format"]]
            lines.extend(f"{field}: {item[field]}" for field in WIRE_FIELDS if field in item)
            return "\n".join(lines) + "\n"
    return None


def parse_result(stdout: str) -> dict | None:
    result: dict[str, str] = {}
    for line in stdout.splitlines():
        if line.startswith(RESULT_PREFIX):
            result["format"] = line.strip()
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result or None


def run_case(case: dict, runner: Path, workspace: Path) -> dict:
    case_id = case["case_id"]
    request = ward_request(case)
    if request is None:
        return {
            "case_id": case_id,
            "execution_status": "NOT_CONSTRUCTIBLE",
            "native_result": None,
            "diagnostic": "case carries no request in the counterparty's format",
        }

    # Absolute, because cwd is about to become this same directory. A relative
    # path handed to the subprocess would be resolved a second time against the
    # new cwd, and the counterparty would be asked for a request that is not
    # where it was told to look.
    work = (workspace / case_id).resolve()
    work.mkdir(parents=True, exist_ok=True)
    request_path = work / "request.wire"
    request_path.write_text(request, encoding="utf-8")

    try:
        completed = subprocess.run(
            [sys.executable, str(runner), str(request_path)],
            cwd=work, shell=False, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "case_id": case_id,
            "execution_status": "EXECUTION_UNAVAILABLE",
            "native_result": None,
            "diagnostic": f"the counterparty did not return within {TIMEOUT_SECONDS}s",
        }

    status = EXIT_STATUS.get(completed.returncode, "EXECUTION_FAILED")
    return {
        "case_id": case_id,
        "execution_status": status,
        "native_result": parse_result(completed.stdout) if completed.returncode == 0 else None,
        "request_sha256": sha256_file(request_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--party-id", default="GLYPHLOCK")
    parser.add_argument("--source-repository", default="")
    parser.add_argument("--source-commit", default="")
    args = parser.parse_args(argv)

    if not args.runner.is_file():
        print(json.dumps({"status": "EXECUTION UNAVAILABLE",
                          "reason": "the counterparty runner is not present"}))
        return 1

    case_set = json.loads(args.cases.read_text(encoding="utf-8"))
    args.workspace.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)

    results = [run_case(case, args.runner.resolve(), args.workspace)
               for case in case_set["cases"]]

    (args.output / "RESULTS.json").write_text(
        json.dumps({
            "record_kind": "interop-lab-native-results",
            "party_id": args.party_id,
            "case_count": len(results),
            "results": results,
            "non_claims": [
                "These are the counterparty's own results in its own vocabulary.",
                "No comparison, mapping or expectation was consulted to produce them.",
            ],
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    (args.output / "PARTY-DOMAIN.json").write_text(
        json.dumps({
            "record_kind": "interop-lab-party-domain",
            "party_id": args.party_id,
            "source_repository": args.source_repository,
            "source_commit": args.source_commit,
            "runner_sha256": sha256_file(args.runner),
            "isolation": {
                "private_wexp_source_present": False,
                "credential_material_present": False,
                "publication_staging_present": False,
            },
            "non_claims": [
                "This records where the counterparty ran, not that its result is true.",
                "Job separation is the isolation boundary; no stronger claim is made.",
            ],
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({"party_id": args.party_id, "cases": len(results),
                      "statuses": sorted({r["execution_status"] for r in results})},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
