"""A deliberately small reader for this repository's own workflows.

The trust boundary this repository cares about is expressed as a *topology*:
which job holds the credential, which job runs somebody else's code, and what
order the steps come in. That is worth asserting in a test rather than in a
comment. A full YAML parser is not in the standard library, and taking a
dependency to read four self-authored files would be a worse trade than reading
the narrow subset they use.

The reader understands jobs, the steps inside them, and the raw text of each
step. Anything beyond that is left to ``actionlint`` and to GitHub itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

USES_RE = re.compile(r"^\s*(?:-\s+)?uses:\s*(?P<value>\S+)")
PINNED_USES_RE = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
JOB_RE = re.compile(r"^ {2}(?P<name>[A-Za-z_][A-Za-z0-9_-]*):\s*$")
STEP_RE = re.compile(r"^ {6}-\s")
STEPS_KEY_RE = re.compile(r"^ {4}steps:\s*$")
STEP_NAME_RE = re.compile(r"^ {6}-\s+name:\s*(?P<name>.+?)\s*$")


@dataclass
class Step:
    index: int
    name: str
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def mentions(self, needle: str) -> bool:
        return needle in self.text


@dataclass
class Job:
    name: str
    lines: list[str] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def mentions(self, needle: str) -> bool:
        return needle in self.text

    def step_index(self, needle: str) -> int:
        for step in self.steps:
            if step.mentions(needle):
                return step.index
        raise AssertionError(f"job {self.name!r} has no step mentioning {needle!r}")

    def steps_mentioning(self, needle: str) -> list[Step]:
        return [step for step in self.steps if step.mentions(needle)]


def strip_comments(text: str) -> str:
    """Drop whole-line comments so prose about a risk is not read as the risk."""
    return "\n".join(line for line in text.splitlines()
                     if not line.lstrip().startswith("#"))


def parse_jobs(text: str) -> dict[str, Job]:
    lines = strip_comments(text).splitlines()
    jobs: dict[str, Job] = {}

    in_jobs = False
    current: Job | None = None
    in_steps = False
    step: Step | None = None

    for line in lines:
        if not in_jobs:
            if line.rstrip() == "jobs:":
                in_jobs = True
            continue
        if line.strip() and not line.startswith(" "):
            break  # a new top-level key ends the jobs block

        job_match = JOB_RE.match(line)
        if job_match:
            current = Job(name=job_match.group("name"))
            jobs[current.name] = current
            in_steps = False
            step = None
            continue
        if current is None:
            continue
        current.lines.append(line)

        if STEPS_KEY_RE.match(line):
            in_steps = True
            continue
        if not in_steps:
            continue
        if STEP_RE.match(line):
            name_match = STEP_NAME_RE.match(line)
            step = Step(index=len(current.steps),
                        name=name_match.group("name") if name_match else "<unnamed>")
            current.steps.append(step)
            step.lines.append(line)
            continue
        if step is not None:
            step.lines.append(line)

    return jobs


def triggers(text: str) -> list[str]:
    """Top-level trigger names, for both the block and inline ``on:`` forms."""
    lines = strip_comments(text).splitlines()
    found: list[str] = []
    inside = False
    for line in lines:
        if not inside:
            if line.startswith("on:"):
                inside = True
                rest = line[len("on:"):].strip()
                if rest.startswith("[") and rest.endswith("]"):
                    found.extend(item.strip() for item in rest[1:-1].split(",") if item.strip())
                elif rest:
                    found.append(rest)
            continue
        if line.strip() and not line.startswith(" "):
            break
        match = re.match(r"^ {2}([A-Za-z_][A-Za-z0-9_]*):", line)
        if match:
            found.append(match.group(1))
    return found


def action_references(text: str) -> list[str]:
    return [match.group("value")
            for match in (USES_RE.match(line) for line in text.splitlines())
            if match]


def is_sha_pinned(reference: str) -> bool:
    return bool(PINNED_USES_RE.match(reference))


def workflow_paths(repo_root: Path) -> list[Path]:
    return sorted((repo_root / ".github" / "workflows").glob("*.yml"))
