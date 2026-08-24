# How an interoperability check is routed

Public, so you can see how your submission will be handled before you make it.

These are **service routes**. They decide who does the work and in what order.
They are **not** WEXP Profiles, Claim Classes, Boundary Classes, Evaluation
Profiles, or verdicts, and they change nothing about what any evidence supports.
A route is an operational decision about people and sequencing.

The rubric is `selfservice/routing.py` and it is exercised in CI by
`tests/test_routing_rubric.py`, so what is written here is what actually runs.

## The three routes

| Route | Said plainly | When |
| --- | --- | --- |
| `SELF_SERVICE` | Run it automatically. | The case matches something already worked out, everything is public and pinned to an **admitted** exact commit, and no operating condition is in the way. |
| `ASSISTED_REVIEW` | Review it with us. | The semantics are understood, but something operational is unusual — private evidence, special disclosure handling, no exact revision, an outside dependency. |
| `JOINT_RESEARCH` | Research it with us. | The mapping from your evidence to a bounded WEXP claim is itself the open question. |

## The order the rubric applies

**1. Privacy first.** If the case needs private evidence or special disclosure
handling, it goes to `ASSISTED_REVIEW` immediately — *before* anything private
is sent anywhere. This is deliberately checked before everything else. Any other
ordering would mean discussing private material in a public thread and then
deciding it should have been private.

**2. Is the mapping the question?** If nobody has established how this kind of
evidence maps to a bounded WEXP claim, that is `JOINT_RESEARCH`. Running it
automatically would produce a confident-looking answer to a question that has
not been posed properly, which is worse than no answer.

**3. Is everything actually in place?** Public source; an exact revision; that
revision **explicitly admitted** as a source identity; self-contained; public
example material. All five, or it is not the automatic path.

Supplying an exact commit is not the same as that commit being admitted. The
automatic path admits **exact commits, not repositories** — so a known
repository at a commit nobody admitted is reviewed, not run. That is a
deliberate narrowing: admitting a repository would mean admitting whatever
anyone pushes to it.

**4. Otherwise, review.** Known semantics with something operational in the way
is `ASSISTED_REVIEW`, never research. **An unusual operating condition is not a
new scientific question**, and quietly promoting one to the other would inflate
what the research route means.

## You do not pick your route

Your own view of your case is useful input. It is not authority.

The guarantee is structural, not a promise: `route()` never reads a
requested-route field at all, so asking for one cannot change the answer. There
is a test that asserts the field is absent from the parsed source.

## What you get

An **Interop Record**: a scoped, written result. Outcomes may include supported
within a stated scope, supported with qualifiers, underdetermined, mapping
required, semantic disagreement, out of scope, or infrastructure unavailable.

A refusal or a weaker claim is a successful result. An infrastructure problem is
never reported as a semantic one.

## A finding does not change WEXP

If a case appears to expose new semantics, it stops for review and adjudication.
It is not guessed at, and it is not promoted because it ran cleanly.

Operational repetition does not ratify semantics. Commercial interest does not
ratify semantics.

## What is observable, and what is not

Routing is recorded with GitHub-native events — issue labels — so the state of
any submission is visible without tracking anyone.

| State | How it is observed |
| --- | --- |
| `INTAKE_SUBMITTED` | the issue exists, with `interop-intake` |
| `ROUTED_SELF_SERVICE` | label `route:self-service` |
| `ROUTED_ASSISTED` | label `route:assisted` |
| `ROUTED_RESEARCH` | label `route:research` |
| `ACCEPTED_INTO_PROCESS` | label `accepted` |
| `INTEROP_RECORD_PRODUCED` | label `record-produced`, and the record linked in the thread |

Two states in the funnel are **not** honestly observable and are not claimed:

- `ENTRY_VIEWABLE` — GitHub's traffic data needs push access, is a 14-day
  rolling aggregate, and does not attribute views to a link. We can say the page
  exists; we cannot say who saw it.
- `INTAKE_STARTED` — opening an issue form emits no event. Someone who starts
  the form and abandons it leaves no trace, by design.

No tracking pixels. No external analytics. No inferred engagement reported as
measurement. If a number is not a repository event, it does not get quoted.
