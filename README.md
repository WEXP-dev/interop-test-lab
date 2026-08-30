# interop-test-lab

### Want to test your system with WEXP? **[Start here.](START-HERE.md)**

*Or see [what a result looks like](EXAMPLE-INTEROP-RECORD.md) first.*

*Everything below is the engine room. You do not need any of it to ask a question.*

---

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
| tooling | private | private |

`interop-test-subject` is a **synthetic** counterparty: a protocol invented for
this testing and used by nobody for anything. `wexp-ref` is the public WEXP
reference implementation.

Both public inputs are pinned to exact commits in [`pins.json`](pins.json).
Nothing floats.

The pinned `wexp-ref` commit is an **open, unmerged pull-request head**, not a
published `wexp-ref` state. `pins.json` records it as `draft-unmerged` and it
must not be described as a released or canonical part of the reference
implementation. It is public, and it is experimental.

## Two execution domains

A counterparty is somebody else's code. It runs in a job of its own that holds
no credential, no private checkout and no publication staging tree, and it hands
its native result across the boundary as an artifact. The coordination domain
consumes that artifact as data; it never fetches and never executes counterparty
code, before the publication gate or after it.

```
counterparty domain          coordination domain
  counterparty's own code      private tooling, WEXP party
  no secrets                   comparison, publication gate
  no private checkout          consumes declared artifacts only
        └────── native result artifact ──────┘
```

The counterparty's own results are then compared, case by case, against the
results the run recorded for it. A disagreement stops the run: published
evidence must describe a run that actually happened, and a mismatch is an
authority finding rather than a result about either party.

The isolation boundary is job separation — separate runners, separate
filesystems, artifacts as the only channel. That is the property relied on and
it is the only one claimed. It is not a sandbox and not a defence against a
compromise of the hosting platform. See [`SECURITY-INVARIANTS.md`](SECURITY-INVARIANTS.md).

## Private tooling access

Private tooling is fetched at an immutable version using a short-lived,
repository-scoped, read-only credential. The exact private identity is verified
during execution but is intentionally excluded from public evidence. No
credential is committed to this repository, and none is available to the
counterparty domain.

Access and version identity are deliberately separate concerns. The credential
grants *access*. A protected runtime configuration value supplies the *exact
immutable commit* — required, validated, never a branch head and never a
floating ref.

You can verify from this repository that the tooling was exact-pinned; you
cannot learn which commit it was, and the publication gate refuses to ship a
bundle that would tell you.

## Publication

Nothing leaves a run that was not admitted in advance.
[`publication/ALLOWLIST.json`](publication/ALLOWLIST.json) names every
publishable artifact by exact path; a file nobody admitted fails the run. Once
the tree is frozen and manifested, the deny scan runs, the manifest is
re-verified, and only then does the upload happen. There is no `if: always()`
on the upload: a run whose gate refused publishes nothing.

## Running it

The hosted interop leg runs on `workflow_dispatch` or on a push to `main`, both
of which require write access. It has deliberately **no `pull_request` trigger**:
a contributor's pull request cannot start it, and therefore cannot reach the
credential.

Two self-service workflows sit alongside it, and they are triggered differently
on purpose:

- **Request validation** runs on `pull_request`. It holds no secret, mints no
  token, and never executes counterparty code — it reads bytes and computes
  digests. That is exactly why it is safe on a fork's pull request: a submitter
  can find out whether their request conforms without anyone here being involved.
- **Auto-dispatch** runs on `workflow_run`, when validation completes. GitHub
  runs it from the default branch with this repository's own token, so a
  submitter controls neither the code that executes nor the permissions it holds.
  The request is treated as untrusted data throughout: re-hashed and
  re-validated with trusted code before any admission decision. A green pull
  request never causes execution by itself.

The regression suite in
[`.github/workflows/checks.yml`](.github/workflows/checks.yml) also runs on pull
requests, for the same reason: the checks that guard the boundary should run on
exactly the changes most likely to weaken it.

Every step shells out to the same CLI the assisted and manual paths use. There
is no semantic decision inside the YAML — delete the workflow, run the same
commands by hand, and you get the same evidence.

## Results

An infrastructure problem is not a semantic result. If the workflow cannot fetch
its inputs it records that fact and stops, rather than reporting an outcome about
either party. Disagreement, underdetermination and a missing mapping are all
legitimate results; only a broken procedure is a failure.

## Licence

Apache-2.0 — see [`LICENSE`](LICENSE).

It covers what is in this repository: the integration workflows, the admission
and routing implementation, the schemas, the regression suite, and the synthetic
pilot source. It covers nothing that is only referenced from here. The private
tooling is fetched at an immutable version and is not vendored, so it is not
licensed by this file. The counterparty carries its own licence in its own
repository.

## Status

Prototype-000 is an **experimental, disposable architectural prototype**. It is
not production tooling, it carries no security certification, and it may be
discarded rather than maintained if its abstraction boundary turns out to be
wrong.
