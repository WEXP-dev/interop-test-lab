# What the automatic path has actually been run against

The self-service path is described elsewhere in this repository as something
that works. This file records exactly what has been run, so that the
description cannot be read as more than it is.

## What ran

A synthetic pilot, `SS-PILOT-001`, on 2026-08-24. The counterparty was this
repository's own `selfservice/pilot-source/` tree, pinned to an exact commit and
admitted in advance by `selfservice/envelopes/ENVELOPE-PILOT-001.json`. One
case. One authorized run. The party identifies itself in its own output as
`SYNTHETIC-PILOT-PARTY`.

The exercise covered the control plane end to end: a request was validated, a
ticket was issued against the active envelope and spent once against the
durable ledger, the counterparty entrypoint ran in a domain of its own, and a
terminal record was produced.

Public workflow runs in this repository, all on 2026-08-24:

| Workflow | Run |
| --- | --- |
| Self-service admit and run | `32710096546` |
| Self-service auto-dispatch | `32713915779`, `32714571790`, `32715019713` |

The negative controls ran too, and are equally public. Each refused in the
admission domain, before any counterparty code ran, and said why:

| Run | Refusal recorded in the public log |
| --- | --- |
| `32715467402` | `envelope is not ACTIVE (status='SUSPENDED'); suspending an envelope is the rollback path and it works` |
| `32714268452` | `ticket already consumed; replay refused` |
| `32714142231` | `request is outside the envelope: requested claim ceiling is not the ceiling this envelope grants; a ceiling is granted, never declared by the request` |

A refusal is recorded here as a workflow failure. That is the intended shape: a
run that must not proceed does not proceed.

## What that did not establish

- **No external system has used this path.** The counterparty was this
  repository's own synthetic pilot tree. Not GLYPHLOCK, not a third party.
- **No semantic result was produced.** The pilot's own terminal record carries
  `SEMANTIC_RESULT: NOT_EVALUATED`, because no interoperability question was
  asked. A workflow that succeeded is infrastructure, not semantics.
- **No interoperability, conformance or certification claim** follows from any
  of it, and none is made.
- **Admission is mechanical; the envelope behind it is not.** The envelope is a
  human authority decision taken once, in advance. Automation removed the
  per-request coordination, not the authority.

## Current access (2026-10-18)

The artifact listings for runs `32710096546` and `32713915779` each returned
`total_count: 0` when checked on 2026-10-18. Their original evidence bundles
cannot currently be downloaded from those listings. The run metadata and this
historical account remain public; they are not substitutes for the full bundle.

This is a limit on present evidence access, not a finding that the historical
exercise failed. The envelope's `ACTIVE` status still concerns admission to its
explicitly authorized synthetic class; artifact expiry does not widen or revoke
that authority. The public intake is experimental and has no response-time
commitment.

Full independent repetition has an additional limit: [pins.json](../pins.json)
identifies private tooling with runtime-verified private version identity. Its
public `wexp-ref` input is pinned to an exact `draft-unmerged` commit. A reader
without the private tooling cannot reproduce the complete laboratory execution
from the public repositories alone. Neither that pin nor the pilot envelope is
changed by this status update.

## Retention and any future public example

The original evidence bundle was stored as a GitHub Actions artifact with
retention ending **2026-09-23**. The run metadata remains public; the two
checked artifact listings no longer provide the bundle. Publishing the bundle into this repository would need a publication
decision the pilot ticket did not grant — `publication_authorized` is `false` on
`SS-PILOT-TICKET-001` — and this project does not publish run output that was
not admitted in advance.

If a durable public artifact is wanted, the correct route is a fresh run whose
request admits publication, not a retroactive one.

Any future public example needs a new scoped request, permitted public outputs,
and a durable carrier with a manifest and reproduction instructions. Availability
of such a bundle would allow inspection of its contents; a claim of independent
execution reproducibility additionally needs accessible tooling and dependencies.
This status update authorizes neither a new run nor publication of old outputs.
