# interop-test-lab

**Public.** An experimental interoperability test lab for Prototype-000.

This repository holds the integration workflow and the experiment state. It is
where an exercise is *run*, not where the framework lives.

## What is not here

**The generic interop core does not live in this repository.** Neither do the
party adapters. Vendoring them here would make this repository the home of
something it is only supposed to consume, and the whole point of the exercise is
that the engine and the counterparty are separable.

## The three inputs

| | Repository | Visibility |
|---|---|---|
| counterparty | [`WEXP-dev/interop-test-subject`](https://github.com/WEXP-dev/interop-test-subject) | public |
| WEXP party | [`WEXP-dev/wexp-ref`](https://github.com/WEXP-dev/wexp-ref) | public |
| tooling | `WEXP-dev/wexp-work` | private |

`interop-test-subject` is a **synthetic** counterparty: a protocol invented for
this testing and used by nobody for anything. `wexp-ref` is the public WEXP
reference implementation.

Both public inputs are pinned to exact commits in [`pins.json`](pins.json).
Nothing floats.

## Private tooling access

The tooling stays private. This workflow reaches it through the **WEXP
Automation** GitHub App:

- the App is installed only on `WEXP-dev/wexp-work`;
- it holds **Contents: Read-only** and nothing else;
- a **short-lived installation token** is minted at runtime and used for that
  one fetch;
- the token is never persisted, never printed, and never written to an artifact;
- **no App credential or token is committed to this repository.**

Access and version identity are deliberately separate concerns. The App grants
*access*. A protected runtime configuration value supplies the *exact immutable
commit* to check out — required, validated, never a branch head and never a
floating ref.

**The private commit identity is not part of this public genesis and is not
printed by the workflow.** You can verify from this repository that the tooling
was exact-pinned; you cannot learn which commit it was.

## Running it

The workflow runs on `workflow_dispatch` or on a push to `main`, both of which
require write access. There is deliberately **no `pull_request` trigger**: a
contributor's pull request cannot start a run, and therefore cannot reach the
App credential.

Every step shells out to the same CLI the assisted and manual paths use. There
is no semantic decision inside the YAML — delete the workflow, run the same
commands by hand, and you get the same evidence.

## Results

An infrastructure problem is not a semantic result. If the workflow cannot fetch
its inputs it records that fact and stops, rather than reporting an outcome about
either party. Disagreement, underdetermination and a missing mapping are all
legitimate results; only a broken procedure is a failure.

## Status

Prototype-000 is an **experimental, disposable architectural prototype**. It is
not production tooling, it carries no security certification, and it may be
discarded rather than maintained if its abstraction boundary turns out to be
wrong.
