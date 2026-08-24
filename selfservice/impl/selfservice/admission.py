"""Envelope verification, ticket issue, and ticket consumption.

These are the trusted steps. They run only where a human with write access has
already decided to run them, and they still refuse rather than repair.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from selfservice.model import (  # noqa: E402
    CHARTER_INVARIANTS, Refused, SHA256_RE, canonical_sha256, load_exact, sha256_bytes,
)

# ---------------------------------------------------------------- envelope

def verify_envelope(envelope_path: Path, *, expect_provenance: str | None = None) -> dict:
    """An envelope is trusted because of where it lives, not because it says so.

    Authenticity on the free tier rests on the envelope being a file on a
    protected default branch: pull request required, force push blocked, deletion
    blocked. `expect_provenance` records which protected ref the caller resolved
    it from; a caller that cannot state one gets an explicit unverified note
    rather than a silent pass.
    """
    _, env = load_exact(envelope_path)
    if env.get("schema_version") != "wexp-interop-admission-envelope/0.1":
        raise Refused("envelope schema_version is not the supported one")
    if env.get("status") != "ACTIVE":
        raise Refused(f"envelope is not ACTIVE (status={env.get('status')!r}); "
                      "suspending an envelope is the rollback path and it works")
    if env.get("issued_by", {}).get("signature_required") is not True:
        raise Refused("envelope does not require a signature")
    grants = env.get("grants", {})
    if grants.get("runs_per_request") != 1:
        raise Refused("envelope grants other than exactly one run per request")
    if not env.get("expiry"):
        raise Refused("envelope has no expiry")
    env["_provenance"] = expect_provenance or "UNVERIFIED — caller stated no protected ref"
    return env


def request_within_envelope(request: dict, receipt: dict, envelope: dict) -> list[str]:
    """Every reason this request is outside the envelope. Empty means inside."""
    out = []
    admits = envelope["admits"]
    repo = request["counterparty"]["repository"]
    if repo not in admits["counterparty_repositories"]:
        out.append(f"counterparty repository not admitted: {repo}")
    for case in request["experiment"]["cases"]:
        if case["sha256"] not in admits["case_set_digests"]:
            out.append(f"case digest not admitted: {case['sha256'][:12]}")
    if request["experiment"]["comparison_policy"]["sha256"] not in admits["comparison_policy_digests"]:
        out.append("comparison policy digest not admitted")
    for p in request["publication"]["requested_paths"]:
        cls = p.split("/")[0] if "/" in p else p
        if cls not in admits["publication_classes"] and p not in admits["publication_classes"]:
            out.append(f"publication path outside admitted classes: {p}")
    asked = request["experiment"]["requested_claim_ceiling"]
    granted = envelope["grants"]["max_claim_ceiling"]
    if asked != granted:
        out.append("requested claim ceiling is not the ceiling this envelope grants; "
                   "a ceiling is granted, never declared by the request")
    if receipt["outcome"] != "VALIDATED":
        out.append(f"receipt outcome is {receipt['outcome']}, not VALIDATED")
    if receipt["wexp_side_classification"]["routine"] is not True:
        out.append("receipt does not classify this request as routine")
    return out


# ---------------------------------------------------------------- ticket

def issue_ticket(request_path: Path, receipt_path: Path, envelope_path: Path,
                 *, ticket_id: str, provenance: str | None = None) -> dict:
    raw_req, request = load_exact(request_path)
    raw_rec, receipt = load_exact(receipt_path)
    envelope = verify_envelope(envelope_path, expect_provenance=provenance)

    if receipt["request_sha256"] != sha256_bytes(raw_req):
        raise Refused("receipt does not describe this request; the bytes changed "
                      "after validation and a changed request is a different request")
    if receipt["validator"]["privileged"] is not False or receipt["validator"]["secrets_available"] is not False:
        raise Refused("receipt claims a privileged validator")

    outside = request_within_envelope(request, receipt, envelope)
    if outside:
        raise Refused("request is outside the envelope: " + "; ".join(outside))

    return {
        "schema_version": "wexp-interop-admission-ticket/0.1",
        "ticket_id": ticket_id,
        "request_sha256": receipt["request_sha256"],
        "validation_receipt_sha256": sha256_bytes(raw_rec),
        "envelope_id": envelope["envelope_id"],
        "runs_authorized": 1,
        "semantic_endorsement": False,
        "publication_authorized": False,
        "non_claims": [
            "Admission is a mechanical decision that this exact request may run once.",
            "It says nothing about what the result will mean.",
        ],
    }


# ---------------------------------------------------------------- consumption

def consume_ticket(ticket_path: Path, ledger_path: Path, *,
                   request_path: Path, envelope_path: Path) -> dict:
    """Spend a ticket exactly once.

    The ledger is a file on a protected branch. That is the only durable
    single-use primitive the free tier actually offers: the Actions cache is
    evictable and artifacts expire, so neither can carry a security property.
    """
    raw_t, ticket = load_exact(ticket_path)
    raw_req, request = load_exact(request_path)
    envelope = verify_envelope(envelope_path, expect_provenance="ledger check")

    if ticket.get("schema_version") != "wexp-interop-admission-ticket/0.1":
        raise Refused("ticket schema_version is not the supported one")
    if ticket.get("runs_authorized") != 1:
        raise Refused("ticket does not authorize exactly one run")
    if ticket["envelope_id"] != envelope["envelope_id"]:
        raise Refused("ticket was issued against a different envelope")
    if ticket["request_sha256"] != sha256_bytes(raw_req):
        raise Refused("ticket does not cover these request bytes")
    if not SHA256_RE.fullmatch(ticket["request_sha256"]):
        raise Refused("ticket request identity is not a sha256")

    ticket_digest = sha256_bytes(raw_t)
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() \
        else {"record_kind": "interop-lab-consumed-tickets", "consumed": []}
    if any(e["ticket_sha256"] == ticket_digest for e in ledger["consumed"]):
        raise Refused("ticket already consumed; replay refused")
    if any(e["request_sha256"] == ticket["request_sha256"] for e in ledger["consumed"]):
        raise Refused("this request identity has already been dispatched once")

    ledger["consumed"].append({"ticket_sha256": ticket_digest,
                               "request_sha256": ticket["request_sha256"],
                               "envelope_id": ticket["envelope_id"]})
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"status": "CONSUMED", "ticket_sha256": ticket_digest,
            "request_sha256": ticket["request_sha256"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("issue")
    t.add_argument("--request", type=Path, required=True)
    t.add_argument("--receipt", type=Path, required=True)
    t.add_argument("--envelope", type=Path, required=True)
    t.add_argument("--ticket-id", required=True)
    t.add_argument("--provenance")
    t.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("consume")
    c.add_argument("--ticket", type=Path, required=True)
    c.add_argument("--request", type=Path, required=True)
    c.add_argument("--envelope", type=Path, required=True)
    c.add_argument("--ledger", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "issue":
            out = issue_ticket(a.request, a.receipt, a.envelope,
                               ticket_id=a.ticket_id, provenance=a.provenance)
            a.out.parent.mkdir(parents=True, exist_ok=True)
            a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps({"status": "ADMITTED", "ticket_id": out["ticket_id"],
                              "request_sha256": out["request_sha256"]}, sort_keys=True))
        else:
            print(json.dumps(consume_ticket(a.ticket, a.ledger, request_path=a.request,
                                            envelope_path=a.envelope), sort_keys=True))
    except Refused as exc:
        print(json.dumps({"status": "REFUSED", "reason": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
