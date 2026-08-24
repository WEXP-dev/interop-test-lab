# Your system says an action happened. What can you actually claim?

Software records things: a receipt, an attestation, a log line, a signed result,
an agent reporting "done". Those records get treated as if they settle what
happened. Often they support something narrower than the claim being made on
them — and the gap only shows up when somebody disputes it.

**WEXP helps you find that boundary before someone else does**, and write it
down in a way you can hand to a reviewer, an auditor, or a partner.

**→ [Start an interoperability check](https://github.com/WEXP-dev/interop-test-lab/issues/new?template=interop-check.yml)**

*Reading this is public. Submitting the form needs a GitHub account.*

---

## A 20-second example

> **The claim** — an agent reports that it completed action X.
>
> **The evidence** — one or more signed records exist, produced at some
> particular place, by some particular component, under some particular
> conditions.
>
> **The WEXP question** — what claim can those records support, *given where and
> how they were witnessed*?
>
> **A possible finding** — the records may support a narrower statement than "X
> completed". They may be underdetermined. Or the evidence may sit at a boundary
> that cannot reach the stronger claim at all.
>
> *Illustrative example — not a normative WEXP result. What any particular
> evidence supports is exactly the thing that has to be examined, not assumed.*

## What you can bring

Any system or specification that produces evidence about an action or a result.
Whether it can be run automatically depends on the route — see below.

You do not need to know any WEXP terminology to ask. The vocabulary can wait
until it is useful to you.

## What you need to provide

Only what you already have: what the system is called, a public source if there
is one, what evidence it produces, and what you want to find out. "Not sure" is
an acceptable answer to most of it.

**Do not send secrets, credentials, private keys, tokens, or confidential
material.** The form is a public issue. If your case needs private handling, say
so — and send nothing private until we confirm whether a suitable route is available.

## What happens after you submit

We first determine which route applies. Routing is determined from the case
itself, not from requester preference.

**Run it automatically** — for a case already covered by a pre-authorized test
class. The automatic path exists and has been demonstrated end to end, but it is
available *only* for classes that have already been explicitly admitted.

**Review it with us** — for known semantics with operating conditions outside
the automated class: private evidence, special disclosure handling, an
unpinned source.

**Research it with us** — where the mapping from your evidence to a bounded WEXP
claim is itself the open question. Running that automatically would answer a
question nobody had posed properly.

**At this early stage, most new external systems will begin with review or joint
research.** Cases that require review are handled by hand, and this is an
experimental public intake: no response-time commitment is offered yet.

The routing rubric is public: [`ROUTING.md`](ROUTING.md).

## What you get

A **WEXP Interop Record**: a scoped, written result. Not a badge, not a pass
mark. It states the question, what was examined, the boundary the evidence was
witnessed at, what is supported within that scope, and — explicitly — what is
not established.

Outcomes may include supported within a stated scope, supported with qualifiers,
underdetermined, mapping required, semantic disagreement, out of scope, or
infrastructure unavailable.

**A refusal or a weaker claim is a successful result.** If the honest answer is
"this evidence supports less than you hoped", that is the answer, and it is
worth more than a generous one.

There is a worked example of what one looks like:
[`EXAMPLE-INTEROP-RECORD.md`](EXAMPLE-INTEROP-RECORD.md).

## The terminology, now that it is useful

WEXP is a **claim-strength layer for digital execution evidence**. It helps
determine *how strong a claim execution evidence can support, given where and
how it was witnessed*.

WEXP Interop examines whether evidence from another system can support a bounded
WEXP claim **without either side giving up authority over its own semantics**.
Your specification stays yours. Ours stays ours.

Every claim has a **Boundary Ceiling** — the strongest claim the evidence can
support from the boundary at which it was witnessed. Piling up more evidence of
the same kind, from the same insufficient boundary, does not by itself lift that
ceiling. Finding out where your ceiling sits is usually the useful result.

## What WEXP does not claim

- WEXP does **not** tell you what your evidence proves.
- WEXP does **not** prove that execution happened.
- There is **no** compatibility certification, and **no** badge.
- Nothing here is **universally interoperable**, and no result generalizes past
  the scope it names.
- None of this is **production-ready**. It is an experimental prototype.
- WEXP does **not** validate another specification as correct. Your semantics
  are not on trial.

**A new interop finding does not automatically change WEXP.** If your case looks
like it exposes new semantics, it stops for review and adjudication rather than
being guessed at or quietly adopted. Repetition does not ratify semantics.
Neither does commercial interest.

## Start

**→ [Start an interoperability check](https://github.com/WEXP-dev/interop-test-lab/issues/new?template=interop-check.yml)**

Reading is public; submitting the GitHub form requires a GitHub account. If you
would rather just ask a question first, open the same form and say so in the
last field. That is a fine way to use it.

---

*Technical details, including the experimental prototype this runs on, start at
[`README.md`](README.md). You do not need them to ask a question.*
