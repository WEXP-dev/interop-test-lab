"""Durable single-use ledger persistence for the self-service pilot.

DEPLOYMENT GLUE, not a redesign. `selfservice.admission.consume_ticket` decides
whether a ticket may be spent and writes a local ledger file; this module is the
part that makes that file durable, and nothing here changes an admission rule.

Why a dedicated branch rather than `main`. The reviewed design says a committed
ledger on a protected branch is the only durable single-use primitive the free
tier offers, and that is right about durability. But `main` here carries a
`pull_request` rule whose bypass actors are admins only, so `github-actions[bot]`
cannot commit to it. Requiring a pull request per ledger append would put a human
in every request, which is exactly the property this pilot exists to measure. The
ledger therefore lives on a branch protected against deletion and force-push:
durable, non-evictable, non-expiring, publicly auditable and non-rewritable. What
it does not have is per-append human review, and that was never what made it
durable.

Concurrency is handled by the Contents API `sha` parameter, which is a genuine
compare-and-swap: a second writer holding a stale blob sha gets 409 and fails
closed rather than silently overwriting the first writer's entry.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"


class LedgerConflict(RuntimeError):
    """The ledger moved under us. Fail closed; never retry blindly into a write."""


def _request(method: str, url: str, token: str, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode() or "{}"), resp.status


def fetch(repo: str, branch: str, path: str, token: str):
    """Return (bytes, blob_sha) or (None, None) when the ledger does not exist yet."""
    url = f"{API}/repos/{repo}/contents/{path}?ref={branch}"
    try:
        body, _ = _request("GET", url, token)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None, None
        raise
    return base64.b64decode(body["content"]), body["sha"]


def put(repo: str, branch: str, path: str, token: str, content: bytes, expected_sha, message: str):
    """Compare-and-swap. `expected_sha` None means create-if-absent."""
    payload = {
        "message": message,
        "content": base64.b64encode(content).decode(),
        "branch": branch,
    }
    if expected_sha:
        payload["sha"] = expected_sha
    url = f"{API}/repos/{repo}/contents/{path}"
    try:
        body, _ = _request("PUT", url, token, payload)
    except urllib.error.HTTPError as exc:
        if exc.code in (409, 422):
            raise LedgerConflict(
                f"ledger compare-and-swap refused (HTTP {exc.code}): another run wrote first"
            ) from exc
        raise
    return body["commit"]["sha"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--branch", required=True)
    ap.add_argument("--path", required=True)
    ap.add_argument("--mode", choices=("fetch", "commit"), required=True)
    ap.add_argument("--local", required=True, help="local ledger file to read or write")
    ap.add_argument("--expected-sha-file", help="where the fetched blob sha is stored / read")
    ap.add_argument("--message", default="selfservice: record ticket consumption")
    args = ap.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("::error::no token available for the ledger", file=sys.stderr)
        return 2

    if args.mode == "fetch":
        raw, blob_sha = fetch(args.repo, args.branch, args.path, token)
        if raw is None:
            open(args.local, "wb").write(
                json.dumps({"record_kind": "interop-lab-consumed-tickets", "consumed": []},
                           indent=2, sort_keys=True).encode() + b"\n"
            )
            blob_sha = ""
        else:
            open(args.local, "wb").write(raw)
        if args.expected_sha_file:
            open(args.expected_sha_file, "w").write(blob_sha or "")
        print(f"ledger fetched; blob_sha={blob_sha or '(absent)'}")
        return 0

    expected = ""
    if args.expected_sha_file and os.path.exists(args.expected_sha_file):
        expected = open(args.expected_sha_file).read().strip()
    try:
        commit = put(args.repo, args.branch, args.path, token,
                     open(args.local, "rb").read(), expected or None, args.message)
    except LedgerConflict as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 3
    print(f"ledger committed at {commit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
