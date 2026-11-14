# The intake model, independent of any channel

The GitHub Issue Form is the **current intake adapter**. It is not the identity
of WEXP Interop intake, and nothing about routing depends on it.

This file exists because that claim was easy to make and, until now, impossible
to check: the form's YAML was simultaneously the adapter *and* the de-facto
schema, so moving to a web form or an email-assisted route would have meant
re-deriving what to ask from a GitHub template. The questions are written down
here instead.

## Canonical intake questions

| # | Question | Required | Why it is asked |
| --- | --- | --- | --- |
| 1 | What is the system, specification or project called? | yes | identity, and something to call the case |
| 2 | Where can it be read about? | no | whether a public source exists at all |
| 3 | Which version? | no | whether an identity exists that could later be pinned exactly |
| 4 | What evidence, record or result does it produce? | no | the thing the whole question is about |
| 5 | What do you want to find out? | no | the question being asked, in the asker's words; blank is read as "what can this evidence support?" |
| 6 | What do you think that evidence lets you claim? | no | the gap between belief and support is often the finding |
| 7 | Public example or test material? | no | whether anything can actually be run |
| 8 | What are you unsure about? | no | frequently the most useful field |
| 9 | Does this need private handling? | no | chooses the track: routed to the [private track](PRIVATE-TRACK.md) before any private material moves |

Only the name is required. A submission with a name and one public link is enough for the first
reply to pin bytes, and the rest is worked out in the conversation.

An adapter may accept answers given in advance. The current one does: the address of the form
takes `title` and any field by its id (`name`, `source`, `revision`, `example`), so an invitation
can carry a form that is already filled in. `tools/prefill_link.py` builds such an address. The
person still reads the form and submits it themselves.

## How the answers reach the routing rubric

`selfservice/routing.py` takes a plain dictionary of facts. It contains no
GitHub reference of any kind — no `github`, no `issue`, no `label`, no webhook.
An adapter's only job is to produce these keys:

| Routing key | Established from |
| --- | --- |
| `requires_private_material` | question 9 |
| `special_disclosure_conditions` | question 9, or review |
| `existing_mapping_known` | WEXP-side knowledge, never the submitter's assertion |
| `semantic_mapping_is_the_question` | WEXP-side reading of questions 4–6 |
| `public_source` | question 2 |
| `exact_revision` | question 3 |
| `source_identity_admitted` | the active envelope — **never** the request |
| `self_contained` | questions 4 and 7, plus review |
| `public_example_material` | question 7 |

Two of these are deliberately **not** submitter-supplied.
`existing_mapping_known` and `source_identity_admitted` are determined on the
WEXP side, because a submitter who could set them could route themselves onto
the automatic path.

## The automatic first reply

`tools/intake_ack.py` reads a submission made through the current adapter and
prepares the first reply: the public files it could pin from the links given
(repository, commit, path, SHA-256, size) and the route from `routing.py`. It
takes one fact from the form, the answer to question 9. It quotes nothing the
submitter wrote, fetches from three fixed hosts only (the GitHub API, GitHub raw
content, and the IETF archive of Internet-Draft revisions), and executes nothing
it reads. An Internet-Draft named with its revision is pinned by the SHA-256 of
its archived text. The reply also records what GitHub shows publicly about the
submitting account and the linked repositories (owner, public organization
member, contributor, or no established link); a statement by the submitter about
who they are is never taken from the form. When the submitter edits an open
submission the reply is rebuilt and replaces the earlier one; an edit by anyone
else is ignored. `.github/workflows/intake-acknowledge.yml` runs it in a job that cannot
write, and a second job that never sees the submission posts the result.

## What portability means here, and what it does not

A future web form or email-assisted intake would replace the adapter and reuse
this model and `routing.py` unchanged. That is the intended shape.

It does **not** mean another channel exists. Only the GitHub form does. Nothing
in this file authorizes building a second one.
