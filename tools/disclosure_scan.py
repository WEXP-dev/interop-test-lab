#!/usr/bin/env python3
"""Scan a staged publication tree for disclosure the bundle must not carry.

This is the deny half of the publication decision. The allowlist decides which
files may exist at all; this decides whether the admitted bytes are clean. Both
run, and both must pass.

Three families are checked:

* **secret and credential shapes** — an actual key, token or password. Any hit
  fails closed.
* **personal and local paths** — a developer's filesystem, a home directory, a
  private cloud mount. Any hit fails closed.
* **protected values supplied at runtime** — the private tooling pin and any
  other value named on the command line. Any hit fails closed.
* **strategic product vocabulary** — a review trigger, not a proof of leakage.
  A hit fails closed *unless* the exact (path, keyword) pair carries a written
  exception in the allowlist. A word is never rejected silently and never
  accepted silently.

Usage:

    python3 tools/disclosure_scan.py --staging build/evidence \
        --allowlist publication/ALLOWLIST.json \
        --protected-value-file build/protected-values.txt \
        --report build/evidence-scan.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from staging import GateFailure, walk_staging  # noqa: E402

SECRET_PATTERNS: list[tuple[str, str]] = [
    ("private-key-block", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("github-pat-classic", r"\bghp_[A-Za-z0-9]{20,}"),
    ("github-pat-fine", r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    ("github-oauth", r"\bgho_[A-Za-z0-9]{20,}"),
    ("github-app-token", r"\bghs_[A-Za-z0-9]{20,}"),
    ("openai-key", r"\bsk-[A-Za-z0-9_\-]{20,}"),
    ("aws-access-key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("google-api-key", r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    ("slack-token", r"\bxox[abprs]-[0-9A-Za-z-]{10,}"),
    ("authorization-header", r"\bAuthorization\s*:\s*(?:Bearer|Basic)\s+\S{8,}"),
    ("assigned-password", r"(?i)\bpass(?:word|wd)\s*[:=]\s*\S+"),
    ("assigned-secret", r"(?i)\b(?:client_secret|webhook_secret|api[_-]?secret)\s*[:=]\s*\S+"),
    ("pem-block", r"-----BEGIN (?:RSA|DSA|EC|OPENSSH|PGP) "),
]

PATH_PATTERNS: list[tuple[str, str]] = [
    ("posix-home", r"/(?:Users|home)/(?![A-Za-z0-9._-]*(?:runner|_work)\b)[A-Za-z0-9._-]+/"),
    ("windows-home", r"[A-Za-z]:\\Users\\[^\\\s]+"),
    ("macos-volume", r"/Volumes/[A-Za-z0-9 ._-]+"),
    ("icloud-mount", r"Library/CloudStorage"),
    ("google-drive", r"(?:My Drive|GoogleDrive-|Мой диск)"),
    ("onedrive", r"OneDrive"),
    ("dropbox", r"Dropbox"),
    ("ssh-dir", r"(?:^|[\s\"'/])\.ssh/"),
    ("gnupg-dir", r"(?:^|[\s\"'/])\.gnupg/"),
    ("gnupg-private-keys", r"private-keys-v1\.d"),
    ("user-local-share", r"(?:^|[\s\"'/])\.local/share/"),
    ("codex-session", r"\.codex/sessions/"),
]

# A hit here means "a human must look", not "this is a leak". The gate turns
# that into an explicit decision by failing until the pair is written down.
STRATEGIC_KEYWORDS: list[str] = [
    "PAIKernel", "PAIkernel", "paikernel",
    "COYL",
    "WitSeal", "witseal", "WitEyes", "WitGate",
    "equity", "pricing", "customer", "funding",
    "commercial roadmap", "monetisation", "monetization",
    "term sheet", "cap table",
]

#: Repositories that are already public, and may therefore be named in a
#: bundle. The rule is stated this way round on purpose: enumerating the private
#: repositories here would publish the inventory this scanner exists to protect,
#: and would miss any repository created after it was written.
PUBLIC_REPOSITORIES: frozenset[str] = frozenset({
    ".github", "interop-test-lab", "interop-test-subject",
    "wexp-interop", "wexp-ref", "wexp-spec", "wexp-vectors",
})

#: An owner/name reference to any repository in the WEXP organisation.
ORG_REPOSITORY_RE = re.compile(r"\bWEXP-dev/([A-Za-z0-9._-]+)")

SECRET_RE = [(name, re.compile(pattern)) for name, pattern in SECRET_PATTERNS]
PATH_RE = [(name, re.compile(pattern)) for name, pattern in PATH_PATTERNS]

# A 40-hex string that is not one of the public pins is a candidate private
# commit identity. The gate is told the public pins; everything else of that
# shape is refused.
GIT_SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def load_protected_values(paths: list[Path], inline: list[str]) -> list[str]:
    values = [value.strip() for value in inline if value.strip()]
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise GateFailure(f"cannot read protected value file {path}: {exc}") from exc
        values.extend(line.strip() for line in text.splitlines() if line.strip())
    return values


#: Every family this scanner can report. A caller may ask for a subset: the
#: publication bundle is held to all of them, while the repository's own tracked
#: tree is held to the ones that are wrong wherever they appear. A README that
#: names a private repository on purpose is a disclosure decision, recorded in
#: the README; a committed credential is never a decision.
ALL_FAMILIES = (
    "secret", "personal-or-local-path", "protected-value", "private-identity",
    "unattributed-commit-identity", "strategic-review-trigger", "undecodable",
)
UNCONDITIONAL_FAMILIES = ("secret", "personal-or-local-path", "undecodable")


def scan(
    staging: Path,
    *,
    allowlist: dict,
    protected_values: list[str],
    public_pins: list[str],
    families: tuple[str, ...] = ALL_FAMILIES,
    exclude: frozenset[str] = frozenset(),
) -> dict:
    staging = staging.resolve()
    wanted = frozenset(families)
    exceptions = {
        (item["path"], item["keyword"])
        for item in allowlist.get("strategic_review_exceptions", [])
    }
    # Every 40-hex value that may legitimately appear: the pins the caller
    # declares at runtime, plus any value the allowlist writes down with a
    # reason. Anything else of that shape is treated as a candidate private
    # commit identity and refused.
    known_shas = {sha.lower() for sha in public_pins}
    known_shas.update(
        str(item["id"]).lower()
        for item in allowlist.get("declared_object_ids", [])
    )

    findings: list[dict] = []
    reviewed = 0

    skipped: list[str] = []
    for relative in walk_staging(staging):
        if relative in exclude:
            skipped.append(relative)
            continue
        path = staging / relative
        text = read_text(path)
        if text is None:
            if "undecodable" not in wanted:
                continue
            findings.append({
                "severity": "FAIL",
                "family": "undecodable",
                "path": relative,
                "detail": "not UTF-8 text; a publication bundle carries only readable evidence",
            })
            continue
        reviewed += 1
        for number, line in enumerate(text.splitlines(), 1):
            for name, rx in (SECRET_RE if "secret" in wanted else ()):
                if rx.search(line):
                    findings.append({
                        "severity": "FAIL", "family": "secret", "rule": name,
                        "path": relative, "line": number,
                    })
            for name, rx in (PATH_RE if "personal-or-local-path" in wanted else ()):
                if rx.search(line):
                    findings.append({
                        "severity": "FAIL", "family": "personal-or-local-path",
                        "rule": name, "path": relative, "line": number,
                    })
            for value in (protected_values if "protected-value" in wanted else ()):
                if value and value in line:
                    findings.append({
                        "severity": "FAIL", "family": "protected-value",
                        "rule": "runtime-protected-value", "path": relative,
                        "line": number,
                    })
            for name in (ORG_REPOSITORY_RE.findall(line)
                         if "private-identity" in wanted else ()):
                if name.rstrip(".") not in PUBLIC_REPOSITORIES:
                    findings.append({
                        "severity": "FAIL", "family": "private-identity",
                        "rule": "non-public-organisation-repository",
                        "path": relative, "line": number,
                        "detail": ("a repository in the organisation that is not on "
                                   "the declared public list"),
                    })
            for sha in (GIT_SHA_RE.findall(line)
                        if "unattributed-commit-identity" in wanted else ()):
                if sha.lower() not in known_shas:
                    findings.append({
                        "severity": "FAIL", "family": "unattributed-commit-identity",
                        "rule": "unknown-40-hex-object-id", "path": relative,
                        "line": number,
                        "detail": "a 40-hex object id that is not a declared public pin",
                    })
            for keyword in (STRATEGIC_KEYWORDS
                            if "strategic-review-trigger" in wanted else ()):
                if keyword in line and (relative, keyword) not in exceptions:
                    findings.append({
                        "severity": "FAIL", "family": "strategic-review-trigger",
                        "rule": keyword, "path": relative, "line": number,
                        "detail": (
                            "a strategic-vocabulary hit is a review trigger, not a "
                            "proof of leakage; admit it by writing an explicit "
                            "strategic_review_exceptions entry, or remove it"
                        ),
                    })

    return {
        "record_kind": "interop-lab-disclosure-scan",
        "status": "CLEAN" if not findings else "FAIL",
        "files_reviewed": reviewed,
        "families_applied": sorted(wanted),
        "files_excluded": sorted(skipped),
        "findings": findings,
        "non_claims": [
            "A CLEAN result means no declared pattern matched the staged bytes.",
            "It is not a proof that the bundle is free of every possible disclosure.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--allowlist", type=Path, required=True)
    parser.add_argument("--protected-value-file", type=Path, action="append", default=[])
    parser.add_argument("--protected-value", action="append", default=[])
    parser.add_argument("--public-pin", action="append", default=[])
    parser.add_argument(
        "--families", default="all",
        choices=("all", "unconditional"),
        help="all: every rule, for a publication bundle. unconditional: the rules "
             "that are wrong wherever they appear, for this repository's own tree.")
    parser.add_argument(
        "--exclusions", type=Path,
        help="a written list of paths this scan does not apply to, with reasons")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    try:
        allowlist = json.loads(args.allowlist.read_text(encoding="utf-8"))
        protected = load_protected_values(args.protected_value_file, args.protected_value)
        exclude: frozenset[str] = frozenset()
        if args.exclusions:
            document = json.loads(args.exclusions.read_text(encoding="utf-8"))
            exclude = frozenset(item["path"] for item in document["excluded"])
        report = scan(
            args.staging,
            allowlist=allowlist,
            protected_values=protected,
            public_pins=args.public_pin,
            families=ALL_FAMILIES if args.families == "all" else UNCONDITIONAL_FAMILIES,
            exclude=exclude,
        )
    except (GateFailure, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"record_kind": "interop-lab-disclosure-scan",
                          "status": "FAIL", "reason": str(exc)}, sort_keys=True))
        return 1

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
    # The findings name paths and rules, never the matched bytes: a scanner that
    # prints what it found is a scanner that publishes what it found.
    print(json.dumps({k: v for k, v in report.items() if k != "findings"}, sort_keys=True))
    for finding in report["findings"]:
        print(f"  {finding['severity']} {finding['family']} "
              f"{finding.get('rule', '')} {finding['path']}"
              f":{finding.get('line', '')}", file=sys.stderr)
    return 0 if report["status"] == "CLEAN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
