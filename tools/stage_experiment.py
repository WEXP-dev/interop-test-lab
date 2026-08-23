#!/usr/bin/env python3
"""Copy the declared experiment inputs into the tooling checkout, and only those.

The lab holds the experiment state; the tooling holds the engine. Handing the
first to the second is a copy, and a copy of a whole directory is a copy of
whatever happens to be in it. A file added to `experiments/X-001/` — a `run.py`,
an `interop_core/` package, a `sitecustomize.py` — would otherwise land inside
the private checkout and execute there with the credential in scope.

So this copies an exact list of declared inputs and refuses everything else.
Write access to this public repository is still write access, but it no longer
reaches into the private tooling's own tree.

    python3 tools/stage_experiment.py \
        --experiment experiments/X-001 \
        --into tooling/interop/prototypes/prototype-000/experiments/X-001
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

#: The experiment's declared inputs. Data, all of it.
DECLARED_INPUTS = (
    "capabilities.json", "cases.json", "claims.json",
    "expectations.json", "parties.json", "policy.json",
)


class StagingRefused(RuntimeError):
    """The experiment directory carries something that was not declared."""


def stage(experiment: Path, into: Path) -> dict:
    experiment = experiment.resolve()
    if not experiment.is_dir():
        raise StagingRefused(f"no experiment directory at {experiment}")

    present = set()
    for path in sorted(experiment.rglob("*")):
        if path.is_symlink():
            raise StagingRefused(f"symlink in the experiment directory: {path.name}")
        if path.is_dir():
            raise StagingRefused(
                f"the experiment directory holds no subdirectories: {path.name}")
        relative = path.relative_to(experiment).as_posix()
        if relative not in DECLARED_INPUTS:
            raise StagingRefused(
                f"undeclared file in the experiment directory: {relative}. "
                "Only declared JSON inputs cross into the tooling checkout.")
        present.add(relative)

    missing = sorted(set(DECLARED_INPUTS) - present)
    if missing:
        raise StagingRefused(f"the experiment is incomplete: {', '.join(missing)}")

    into.mkdir(parents=True, exist_ok=True)
    staged = []
    for name in DECLARED_INPUTS:
        source = experiment / name
        # Parse before copying: an input that is not JSON has no business
        # reaching a checkout this repository does not own.
        try:
            json.loads(source.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StagingRefused(f"{name} is not readable JSON: {exc}") from exc
        shutil.copyfile(source, into / name)
        staged.append(name)

    return {
        "record_kind": "interop-lab-experiment-staging",
        "status": "STAGED",
        "staged": staged,
        "non_claims": [
            "STAGED means exactly the declared inputs were copied.",
            "It says nothing about whether those inputs describe a good experiment.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--into", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = stage(args.experiment, args.into)
    except (StagingRefused, OSError) as exc:
        print(json.dumps({"record_kind": "interop-lab-experiment-staging",
                          "status": "REFUSED", "reason": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
