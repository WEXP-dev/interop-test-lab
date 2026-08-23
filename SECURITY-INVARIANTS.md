# Security invariants

What this repository guarantees, stated as properties rather than as
mechanisms. The mechanisms live in `.github/workflows/` and `tools/`, and they
are expected to change; these should not, and each has a test that fails if it
does.

## 1. Externally controlled code never shares a domain with private material

Code supplied by a counterparty runs in a job that holds no credential, no
private checkout and no publication staging tree. It crosses into the
coordination domain as a declared artifact and never as code.

The coordination domain neither fetches nor executes counterparty code — before
the publication gate or after it.

*Checked by* `tests/test_workflow_topology.py`, and exercised end to end by a
synthetic hostile participant in `tests/test_hostile_counterparty.py`, which
attempts to read a private marker, enumerate sibling checkouts, read
out-of-contract environment, write into staging, mutate a staged artifact, and
print a protected value. A co-located control reproduces the topology this
repository used to have, so the refusals mean something.

## 2. The disclosure gate is the last thing that can change the evidence

In order: all semantic execution completes, declared outputs are collected, the
staging tree is frozen against an exact allowlist, a manifest is written, the
deny scan runs, the manifest is re-verified, and only then does the artifact
upload. After the manifest is written nothing mutates the tree, no counterparty
code runs, and no semantic transformation occurs.

The upload step carries no `if: always()`. A run whose gate refused publishes
nothing.

*Checked by* `tests/test_workflow_topology.py` and `tests/test_post_gate_check.py`.

## 3. Publication is allowlist-first

`publication/ALLOWLIST.json` names every admissible artifact by exact path.
Wildcards are refused, because a wildcard is how an unrevealed fixture reaches
a bundle nobody meant to put it in. A file present in staging and absent from
the allowlist fails the run; a file admitted and absent from staging is
reported, because a party that did not run is a legitimate state.

*Checked by* `tests/test_publication_gate.py`.

## 4. The private tooling's version identity is not published

The exact private commit is verified during execution and is refused everywhere
in the staged bundle, along with credential shapes, personal and local
filesystem paths, private repository names, and any 40-hex object id that is
not a declared public pin.

The scanner reports the rule and the path. It never reports the matched bytes.

*Checked by* `tests/test_disclosure_scan.py`.

## 5. Strategic vocabulary is a review trigger, not an automatic verdict

A product or commercial term in a staged artifact fails the run until a human
writes down why that exact path may carry that exact word. Nothing is rejected
silently and nothing is admitted silently.

*Checked by* `tests/test_disclosure_scan.py`.

## 6. The published evidence describes a run that happened

The counterparty's own repository executes in its own domain, and its native
results are compared case by case against the results the run recorded. A
disagreement refuses the run as an authority finding — never as a result about
either party.

*Checked by* `tests/test_ingest_native.py`.

## 7. Infrastructure problems are not semantic results

A missing pin or a missing credential produces `INFRASTRUCTURE EXECUTION
UNAVAILABLE`, explicitly not an experiment failure and not a portability
failure, and no semantic conclusion is drawn.

Conversely, hardening has not turned any legitimate semantic result into an
infrastructure failure. `MAPPING_REQUIRED`, `SEMANTIC_DISAGREEMENT`,
`EXPECTATION_MISMATCH`, `IMPLEMENTATION_LIMIT`, `UNDETERMINED` and the rest
remain reachable terminal outcomes.

*Checked by* `tests/test_semantics_preserved.py` and
`tests/test_party_counterparty.py`.

## What is not claimed

Job separation on hosted infrastructure is the isolation boundary, and it is
the only one claimed. Separate jobs run on separate runners with separate
filesystems, and artifacts are the only channel between them; that is a real
property and it is the one relied on here.

It is not a sandbox, a container escape boundary, or a defence against a
compromise of the hosting platform itself. If a stronger boundary is required
for a future counterparty, this topology is not sufficient and the honest move
is to say so and stop, rather than to describe job separation as isolation it
does not provide.

Prototype-000 performs no operating-system-level information control. That
non-claim is part of the experiment policy and is not weakened by anything here.
