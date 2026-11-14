#!/usr/bin/env python3
"""Run somebody else's Core-02 appraiser on the public corpus, and compare what it returned.

Three steps, each its own command, because they run in different places:

    inputs   trusted. Reads a pinned corpus, checks its digest, and writes the inputs only:
             one normalized input and one profile catalog per case. No expectation leaves it.
    run      runs in the job that holds the external code and nothing else. For each case it
             starts the implementation's command with `--input <file> --profiles <file>` and
             keeps what it printed, as bytes.
    compare  trusted. Reads those bytes as data, never as code, and compares each of the twenty
             result components with the frozen expectation.

The command-line shape is the one wexp-check has: the result as one JSON object on standard
output. Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import threading
from pathlib import Path

#: The corpora an implementation is run on, by the digest of their expanded form.
CORPORA = {
    "WEXP-CORE-02-VECTORS-001": "d5d2c9d54185f04ac59ac2b5642853a6ebd00c3d28a3239d62682186f5df323f",
    "WEXP-CORE-02-VECTORS-002": "9e301333bfdaa4a96068fe44adc0cde3f8eb63bc08f77f164d1d568f609a8bc0",
}
VECTORS_COMMIT = "edd67056873502a2c3cecf5dd2b8db71271c2f57"
CASE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9_])?/[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9_])?$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
MAX_OUTPUT_BYTES = 1024 * 1024
CASE_TIMEOUT_SECONDS = 30
VERDICTS = ("accept", "downgrade", "reject")
PROCESS_RE = re.compile(r"^(?:exit -?[0-9]{1,5}|timeout|could not start|output too large)$")
SET_FIELDS = {"qualifiers", "profile_identifiers", "basis_refs", "reasons", "limitations", "base_findings",
              "qualifier_findings", "recorder_relations", "counter_evidence", "evaluation_scope",
              "profile_evaluation_gaps", "inherited_limitations", "fatal_conditions", "affected_claims",
              "fatal_reasons", "substantive_reasons", "evaluation_gaps", "evaluation_gap_entries",
              "supported_claims", "maximal_supported_claims", "support_entries", "support_relations"}


class Refusal(Exception):
    """A reason the step cannot go on, written for a person."""


def enc(value) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def logical(value, field=None):
    if type(value) is dict:
        return {k: logical(v, k) for k, v in value.items()}
    if type(value) is list:
        items = [logical(v) for v in value]
        return sorted(items, key=enc) if field in SET_FIELDS else items
    return value


def same(a, b) -> bool:
    try:
        return enc(logical(a)) == enc(logical(b))
    except (TypeError, ValueError):
        return False


def load_corpus(path: Path) -> dict:
    data = path.read_bytes()
    corpus = json.loads(data)
    name = corpus.get("id")
    if CORPORA.get(name) != hashlib.sha256(data).hexdigest():
        raise Refusal(f"{path.name}: not one of the pinned corpora, or its bytes differ from the pinned digest")
    for case in corpus["cases"]:
        if not CASE_RE.match(str(case.get("id"))):
            raise Refusal(f"{name}: a case identifier is not letters, digits, hyphens and underscores")
    return corpus


def write_inputs(corpora: list[Path], out: Path) -> dict:
    listing = {}
    for path in corpora:
        corpus = load_corpus(path)
        target = out / corpus["id"]
        target.mkdir(parents=True)
        for case in corpus["cases"]:
            (target / f"{case['id']}.input.json").write_text(json.dumps(case["input"]), encoding="utf-8")
            (target / f"{case['id']}.profiles.json").write_text(
                json.dumps(case.get("profiles", corpus["profiles"])), encoding="utf-8")
        listing[corpus["id"]] = [case["id"] for case in corpus["cases"]]
    (out / "cases.json").write_text(json.dumps(listing, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return listing


def run_one(arguments: list[str], cwd: Path) -> tuple[str, bytes]:
    """Start one case and keep at most the output limit plus one byte of what it printed.

    The output is read as it arrives, so an implementation that prints without end is stopped at
    the limit and does not fill the memory of the job. Standard error is discarded.
    """
    try:
        process = subprocess.Popen(arguments, cwd=str(cwd), stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        return "could not start", b""
    chunks, over = [], threading.Event()

    def drain():
        size = 0
        while True:
            chunk = process.stdout.read1(65536)
            if not chunk:
                return
            keep = chunk[:MAX_OUTPUT_BYTES + 1 - size]
            chunks.append(keep)
            size += len(keep)
            if size > MAX_OUTPUT_BYTES:
                over.set()
                process.kill()
                return

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    try:
        code = process.wait(timeout=CASE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        reader.join(5)
        process.stdout.close()
        return "timeout", b""
    reader.join(5)
    process.stdout.close()
    if over.is_set():
        return "output too large", b"".join(chunks)
    return f"exit {code}", b"".join(chunks)


def run_cases(inputs: Path, out: Path, entry: str, cwd: Path) -> dict:
    command = shlex.split(entry)
    if not command:
        raise Refusal("the entry command is empty")
    listing = json.loads((inputs / "cases.json").read_text(encoding="utf-8"))
    record = {}
    for name, cases in listing.items():
        (out / name).mkdir(parents=True)
        for case in cases:
            arguments = command + ["--input", str((inputs / name / f"{case}.input.json").resolve()),
                                   "--profiles", str((inputs / name / f"{case}.profiles.json").resolve())]
            state, printed = run_one(arguments, cwd)
            (out / name / f"{case}.json").write_bytes(printed)
            record[f"{name}/{case}"] = state
    (out / "run.json").write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return record


def strict_object(pairs):
    keys = [k for k, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError("repeated key")
    return dict(pairs)


def not_a_number(token):
    raise ValueError(f"{token} is not JSON")


def read_process_record(outputs: Path) -> dict:
    """The exit state the run step recorded for each case; empty when there is no usable record."""
    try:
        descriptor = os.open(outputs / "run.json", os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as handle:
            data = handle.read(MAX_OUTPUT_BYTES + 1)
        record = json.loads(data, object_pairs_hook=strict_object) if len(data) <= MAX_OUTPUT_BYTES else {}
    except (OSError, ValueError, RecursionError):
        return {}
    return record if type(record) is dict else {}


def read_output(path: Path):
    """What the implementation printed for one case, as a value, or the reason there is none."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return None, "no output"
    with os.fdopen(descriptor, "rb") as handle:
        if not os.path.isfile(handle.fileno()):
            return None, "no output"
        data = handle.read(MAX_OUTPUT_BYTES + 1)
    if not data.strip():
        return None, "no output"
    if len(data) > MAX_OUTPUT_BYTES:
        return None, "output too large"
    try:
        value = json.loads(data, object_pairs_hook=strict_object, parse_constant=not_a_number)
    except (ValueError, RecursionError) as error:
        return None, "output repeats a key" if str(error) == "repeated key" else "output is not JSON"
    return (value, None) if type(value) is dict else (None, "output is not a JSON object")


def compare(corpora: list[Path], outputs: Path) -> dict:
    report = {"vectors_commit": VECTORS_COMMIT, "sets": {}}
    processes = read_process_record(outputs)
    for path in corpora:
        corpus = load_corpus(path)
        rows, equal = [], 0
        for case in corpus["cases"]:
            expected = case["expected"]
            observed, problem = read_output(outputs / corpus["id"] / f"{case['id']}.json")
            state = processes.get(f"{corpus['id']}/{case['id']}")
            state = state if type(state) is str and PROCESS_RE.match(state) else "not recorded"
            row = {"id": case["id"], "expected_verdict": expected.get("verdict"), "process": state}
            if state != "exit 0":
                # A result printed by a process that did not end normally is not taken as its result.
                row.update({"equal": False, "problem": f"process: {state}"})
            elif problem:
                row.update({"equal": False, "problem": problem})
            else:
                # A component that is absent is not the same as one that is present and null.
                missing = sorted(k for k in expected if k not in observed)
                differing = sorted(k for k in expected if k in observed and not same({k: expected[k]}, {k: observed[k]}))
                extra = len([k for k in observed if k not in expected])
                verdict = observed.get("verdict")
                row.update({"equal": not differing and not missing and not extra, "differing_components": differing,
                            "missing_components": missing,
                            "components_not_in_the_expectation": extra,
                            "observed_verdict": verdict if verdict in VERDICTS else "other"})
            equal += row["equal"]
            rows.append(row)
        report["sets"][corpus["id"]] = {"corpus_sha256": CORPORA[corpus["id"]], "cases": len(rows),
                                        "equal_to_expected": equal, "rows": rows}
    return report


def summary(report: dict, repository: str, commit: str) -> str:
    if not REPOSITORY_RE.match(repository) or not COMMIT_RE.match(commit):
        raise Refusal("the implementation is named by owner/repository and a full commit id")
    lines = ["### Core-02 appraiser run on the public corpus", "",
             f"Implementation `{repository}` at `{commit}`. Corpora from `WEXP-dev/wexp-vectors` at "
             f"`{report['vectors_commit']}`.", "",
             "| Corpus | Cases | Equal to the frozen expectation in all twenty components |", "|---|---|---|"]
    for name, part in report["sets"].items():
        lines.append(f"| `{name}` | {part['cases']} | {part['equal_to_expected']} |")
    different = [(name, row) for name, part in report["sets"].items() for row in part["rows"] if not row["equal"]]
    if different:
        lines += ["", "| Case | Expected verdict | Returned | Differs in |", "|---|---|---|---|"]
        for name, row in different[:60]:
            expected = row["expected_verdict"] if row["expected_verdict"] in VERDICTS else "other"
            if "problem" in row:
                returned, where = row["problem"], ""
            else:
                returned = row["observed_verdict"]
                parts = [f"`{c}`" for c in row["differing_components"]]
                parts += [f"`{c}` (absent)" for c in row["missing_components"]]
                where = ", ".join(parts) or "components outside the expectation"
            lines.append(f"| `{name}` / `{row['id']}` | {expected} | {returned} | {where} |")
        if len(different) > 60:
            lines.append(f"| and {len(different) - 60} more | | | |")
    lines += ["",
              "This says what this implementation returned on these inputs in this run. A difference is a "
              "finding to look at, about the implementation or about the text, and is not a failure of the run. "
              "The corpus does not claim to be a complete test suite for the specification, so equality on every "
              "case is not a statement about the implementation beyond these cases. A case counts as equal only "
              "when the process ended with exit status 0 and printed one JSON object, with no repeated key, that "
              "has every expected component and no other. The implementation ran in a separate job with no secret; "
              "that separation is the only isolation relied on, and the exit states are recorded in that same job. "
              "The expectations are public; "
              "that an implementation was written without reading them is a declaration by its author, which this "
              "run cannot check.", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    step = commands.add_parser("inputs")
    step.add_argument("--corpus", type=Path, action="append", required=True)
    step.add_argument("--out", type=Path, required=True)
    step = commands.add_parser("run")
    step.add_argument("--inputs", type=Path, required=True)
    step.add_argument("--out", type=Path, required=True)
    step.add_argument("--entry-env", default="ENTRY")
    step.add_argument("--cwd", type=Path, required=True)
    step = commands.add_parser("compare")
    step.add_argument("--corpus", type=Path, action="append", required=True)
    step.add_argument("--outputs", type=Path, required=True)
    step.add_argument("--repository-env", default="IMPLEMENTATION")
    step.add_argument("--commit-env", default="IMPLEMENTATION_COMMIT")
    step.add_argument("--result", type=Path, required=True)
    step.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inputs":
            listing = write_inputs(args.corpus, args.out)
            print({name: len(cases) for name, cases in listing.items()})
        elif args.command == "run":
            record = run_cases(args.inputs, args.out, os.environ.get(args.entry_env, ""), args.cwd)
            print(len(record), "cases run;", sum(1 for s in record.values() if s == "exit 0"), "exited 0")
        else:
            report = compare(args.corpus, args.outputs)
            text = summary(report, os.environ.get(args.repository_env, ""), os.environ.get(args.commit_env, ""))
            args.result.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            args.summary.write_text(text, encoding="utf-8")
            print(text)
    except (Refusal, OSError, ValueError, KeyError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
