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
| 4 | What evidence, record or result does it produce? | yes | the thing the whole question is about |
| 5 | What do you want to find out? | yes | the question being asked, in the asker's words |
| 6 | What do you think that evidence lets you claim? | no | the gap between belief and support is often the finding |
| 7 | Public example or test material? | no | whether anything can actually be run |
| 8 | What are you unsure about? | no | frequently the most useful field |
| 9 | Does this need private handling? | no | routed before any private material moves |

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

## What portability means here, and what it does not

A future web form or email-assisted intake would replace the adapter and reuse
this model and `routing.py` unchanged. That is the intended shape.

It does **not** mean another channel exists. Only the GitHub form does. Nothing
in this file authorizes building a second one.
