#!/usr/bin/env python3
"""A synthetic hostile counterparty.

This stands in for a counterparty repository whose owner is not friendly. It
speaks the counterparty wire format well enough to be run like any other party,
and while it is running it tries every reach the trust boundary is supposed to
stop:

    A  read a marker that exists only inside the private tooling checkout
    B  enumerate sibling and private checkout paths
    C  read environment variables outside its declared contract
    D  emit unexpected files into the publication staging tree
    E  modify a staged artifact after the disclosure gate froze it
    F  print a protected marker to the log

None of these are exploits against GitHub. They are the cheapest thing a
malicious participant would actually try, and the point of the exercise is that
the topology makes them uninteresting rather than that the participant is
polite. Every attempt is recorded — successes *and* refusals — so a test can
assert on what happened rather than on the absence of a crash.

This file is a test participant. It is never a party in a real exercise, and it
is never admitted to a publication bundle.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

#: Populated by the harness with the value the boundary is protecting. The
#: hostile party is told the *name* on purpose: a boundary that only holds while
#: the attacker is ignorant is not a boundary.
SENTINEL_ENV = "WEXP_TEST_SENTINEL_BASENAME"

#: Where the harness wants the attempt log. Real counterparties have no such
#: channel; this one has it so the test can read its confession.
REPORT_ENV = "WEXP_HOSTILE_REPORT"

#: Environment names outside this participant's declared contract.
OUT_OF_CONTRACT_ENV = (
    "WEXP_WORK_PIN", "WEXP_AUTOMATION_APP_ID", "WEXP_AUTOMATION_PRIVATE_KEY",
    "GITHUB_TOKEN", "ACTIONS_RUNTIME_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
)

#: Directory names a private tooling checkout would plausibly use.
PRIVATE_CHECKOUT_NAMES = ("tooling", "wexp-work", "private", "interop_core")

STAGING_HINTS = ("build/evidence", "../build/evidence", "../../build/evidence")


#: How far a participant looks. A checkout sits a few levels below the runner
#: workspace, so this is the region a real attacker would actually sweep — and
#: bounding it keeps the probe fast enough to run on every pull request.
ANCESTOR_DEPTH = 4
GLOB_DEPTH = 4


def search_roots() -> list[Path]:
    here = Path.cwd().resolve()
    roots = [here, *here.parents[:ANCESTOR_DEPTH]]
    workspace = os.environ.get("GITHUB_WORKSPACE")
    if workspace:
        roots.append(Path(workspace))
    return roots


def bounded_glob(root: Path, basename: str):
    for depth in range(GLOB_DEPTH + 1):
        pattern = "/".join(["*"] * depth + [basename]) if depth else basename
        try:
            yield from root.glob(pattern)
        except (OSError, ValueError):
            continue


def attempt_read_private_marker(basename: str | None) -> dict:
    """A: find and read a marker that only the private tooling should hold."""
    if not basename:
        return {"attempt": "A", "goal": "read private marker",
                "outcome": "NOT ATTEMPTED", "detail": "no marker name supplied"}
    for root in search_roots():
        for found in bounded_glob(root, basename):
            try:
                return {"attempt": "A", "goal": "read private marker",
                        "outcome": "SUCCEEDED", "path": str(found),
                        "read_bytes": len(found.read_bytes())}
            except OSError:
                continue
    return {"attempt": "A", "goal": "read private marker", "outcome": "REFUSED",
            "detail": "no file with that name was reachable from this domain"}


def attempt_enumerate_private_checkouts() -> dict:
    """B: look for a sibling private checkout next to my own workspace."""
    found: list[str] = []
    for root in search_roots():
        for name in PRIVATE_CHECKOUT_NAMES:
            candidate = root / name
            try:
                if candidate.exists():
                    found.append(str(candidate))
            except OSError:
                continue
    return {"attempt": "B", "goal": "enumerate private checkouts",
            "outcome": "SUCCEEDED" if found else "REFUSED", "found": sorted(set(found))}


def attempt_read_out_of_contract_env() -> dict:
    """C: read environment the contract never promised me."""
    visible = [name for name in OUT_OF_CONTRACT_ENV if os.environ.get(name)]
    return {"attempt": "C", "goal": "read out-of-contract environment",
            "outcome": "SUCCEEDED" if visible else "REFUSED", "visible": visible}


def attempt_emit_into_staging() -> dict:
    """D: drop a file of my choosing into the publication tree."""
    for hint in STAGING_HINTS:
        staging = Path(hint)
        if not staging.is_dir():
            continue
        target = staging / "HOSTILE-EXTRA.json"
        try:
            target.write_text('{"note":"emitted by a hostile participant"}\n',
                              encoding="utf-8")
        except OSError:
            continue
        return {"attempt": "D", "goal": "emit into publication staging",
                "outcome": "SUCCEEDED", "path": str(target)}
    return {"attempt": "D", "goal": "emit into publication staging",
            "outcome": "REFUSED", "detail": "no staging tree was reachable"}


def attempt_mutate_staged_artifact() -> dict:
    """E: rewrite an artifact the gate already froze."""
    for hint in STAGING_HINTS:
        staging = Path(hint)
        if not staging.is_dir():
            continue
        for target in sorted(staging.rglob("*.json")):
            try:
                target.write_text('{"tampered":true}\n', encoding="utf-8")
            except OSError:
                continue
            return {"attempt": "E", "goal": "mutate a staged artifact",
                    "outcome": "SUCCEEDED", "path": str(target)}
    return {"attempt": "E", "goal": "mutate a staged artifact",
            "outcome": "REFUSED", "detail": "no staged artifact was reachable"}


def attempt_print_protected_marker(basename: str | None) -> dict:
    """F: put a protected value on stdout, where logs and artifacts live."""
    for name in OUT_OF_CONTRACT_ENV:
        value = os.environ.get(name)
        if value:
            sys.stdout.write(f"exfiltrated-{name}: {value}\n")
            return {"attempt": "F", "goal": "print a protected marker",
                    "outcome": "SUCCEEDED", "source": name}
    if basename:
        sys.stdout.write(f"searched-for: {basename}\n")
    return {"attempt": "F", "goal": "print a protected marker", "outcome": "REFUSED",
            "detail": "no protected value was present in this domain"}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    basename = os.environ.get(SENTINEL_ENV)

    attempts = [
        attempt_read_private_marker(basename),
        attempt_enumerate_private_checkouts(),
        attempt_read_out_of_contract_env(),
        attempt_emit_into_staging(),
        attempt_mutate_staged_artifact(),
        attempt_print_protected_marker(basename),
    ]

    report_path = os.environ.get(REPORT_ENV)
    if report_path:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(
            json.dumps({"record_kind": "interop-lab-hostile-participant-report",
                        "attempts": attempts}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")

    # Behave like a party as well, so the harness treats this as a participant
    # rather than as a broken runner: a hostile counterparty that fails to run
    # tests nothing.
    if len(argv) != 1 or not Path(argv[0]).is_file():
        sys.stderr.write("usage: hostile_party.py REQUEST\n")
        return 4
    sys.stdout.write(
        "GLYPHLOCK-RESULT/1\n"
        "seal-state: GLYPH_SEALED\n"
        "ward-reached: 99\n"
        "notes: asserted by a hostile participant\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
