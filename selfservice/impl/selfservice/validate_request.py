"""Unprivileged validator. Runs with no secrets, in a context a fork PR can reach.

It answers one question: may this exact request be considered for admission? It
never admits, never dispatches, and never repairs a request into conformance.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from selfservice.model import (  # noqa: E402
    GIT_SHA_RE, REQUEST_SCHEMA_ID, Refused, Result, SHA256_RE,
    canonical_sha256, load_exact, sha256_bytes,
)

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - schema conformance degrades loudly
    Draft202012Validator = None

SCHEMA = Path(__file__).resolve().parents[2] / "INTEROP-REQUEST.schema.json"
MAX_REQUEST_BYTES = 256 * 1024


def _schema_conformance(request: dict) -> list[str]:
    if Draft202012Validator is None:
        raise Refused("jsonschema is required for schema conformance; refusing to "
                      "approximate it with hand-rolled checks")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
            for e in Draft202012Validator(schema).iter_errors(request)]


def _artifact_digests_verify(request: dict, source_root: Path | None) -> list[str]:
    """Each pinned artifact must exist at its path and match its digest.

    Without a source root this is unverifiable, and the validator says so rather
    than passing a check it did not perform.
    """
    pinned = [request["counterparty"]["native_output_schema"],
              request["experiment"]["expectations"],
              request["experiment"]["comparison_policy"],
              *request["experiment"]["cases"]]
    if source_root is None:
        return [f"unverified (no source root supplied): {a['path']}" for a in pinned]
    problems = []
    for a in pinned:
        target = (source_root / a["path"]).resolve()
        try:
            target.relative_to(source_root.resolve())
        except ValueError:
            problems.append(f"escapes source root: {a['path']}"); continue
        if target.is_symlink() or not target.is_file():
            problems.append(f"missing pinned artifact: {a['path']}"); continue
        if sha256_bytes(target.read_bytes()) != a["sha256"]:
            problems.append(f"digest mismatch: {a['path']}")
    return problems


def validate(request_path: Path, *, source_root: Path | None = None,
             entrypoint_root: Path | None = None) -> tuple[dict, Result]:
    raw, request = load_exact(request_path)
    if len(raw) > MAX_REQUEST_BYTES:
        raise Refused("request is implausibly large")

    diagnostics: list[str] = []
    schema_errors = _schema_conformance(request)
    diagnostics += [f"schema: {e}" for e in schema_errors]

    commit_ok = bool(GIT_SHA_RE.fullmatch(str(
        request.get("counterparty", {}).get("commit", ""))))
    if not commit_ok:
        diagnostics.append("counterparty commit is not a full 40-hex object id")

    entry = request.get("counterparty", {}).get("entrypoint", "")
    entry_ok = True
    if entrypoint_root is not None:
        entry_ok = (entrypoint_root / entry).is_file()
        if not entry_ok:
            diagnostics.append(f"entrypoint not present: {entry}")

    digest_problems = _artifact_digests_verify(request, source_root) if not schema_errors else []
    diagnostics += [f"artifact: {p}" for p in digest_problems]
    artifacts_ok = source_root is not None and not digest_problems

    dep = request.get("counterparty", {}).get("dependencies", {})
    closed = (dep.get("network_access_required") is False
              and dep.get("mutable_dependencies") is False
              and dep.get("external_services") == [])
    no_secret = request.get("counterparty", {}).get("requires_secret") is False
    paths_exact = request.get("publication", {}).get("wildcards_permitted") is False

    # The submitter's research_mode is advisory. This is the authoritative call,
    # and it is deliberately conservative: anything the validator cannot fully
    # verify is not routine.
    routine = bool(not schema_errors and commit_ok and entry_ok and artifacts_ok
                   and closed and no_secret and paths_exact
                   and request["experiment"].get("research_mode") is False)
    basis = ("all mechanical checks passed and the submitter did not declare "
             "research mode" if routine else
             "at least one mechanical check did not pass, or research mode was declared")

    if schema_errors or not commit_ok or not entry_ok or digest_problems:
        outcome = "VALIDATION_FAILED"
    elif request["experiment"].get("research_mode") is True:
        outcome = "REQUIRES_DESIGN_REVIEW"
    elif not (closed and no_secret):
        outcome = "REQUIRES_DESIGN_REVIEW"
    elif not artifacts_ok:
        outcome = "VALIDATION_FAILED"
    else:
        outcome = "VALIDATED"

    receipt = {
        "schema_version": "wexp-interop-validation-receipt/0.1",
        "request_sha256": sha256_bytes(raw),
        "request_bytes": len(raw),
        "request_id": request.get("request_id", ""),
        "validator": {"schema_id": REQUEST_SCHEMA_ID,
                      "privileged": False, "secrets_available": False},
        "checks": {
            "schema_conformance": not schema_errors,
            "counterparty_commit_resolves": commit_ok,
            "entrypoint_present": entry_ok,
            "artifacts_digest_verified": artifacts_ok,
            "publication_paths_exact": paths_exact,
            "no_secret_required": no_secret,
            "closed_dependency_posture": closed,
        },
        "outcome": outcome,
        "wexp_side_classification": {"routine": routine, "basis": basis},
        "diagnostics": diagnostics,
        "non_claims": [
            "A VALIDATED receipt is not an admission and authorizes nothing.",
            "The digest here is the request identity for every later state.",
        ],
    }
    return receipt, Result(outcome, diagnostics)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--request", type=Path, required=True)
    ap.add_argument("--source-root", type=Path)
    ap.add_argument("--entrypoint-root", type=Path)
    ap.add_argument("--receipt", type=Path)
    a = ap.parse_args(argv)
    try:
        receipt, result = validate(a.request, source_root=a.source_root,
                                   entrypoint_root=a.entrypoint_root)
    except Refused as exc:
        print(json.dumps({"outcome": "VALIDATION_FAILED", "reason": str(exc)}))
        return 1
    if a.receipt:
        a.receipt.parent.mkdir(parents=True, exist_ok=True)
        a.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    print(json.dumps({k: receipt[k] for k in
                      ("outcome", "request_sha256", "request_bytes")}, sort_keys=True))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
