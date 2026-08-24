# Example: what a WEXP Interop Record looks like

> **SYNTHETIC EXAMPLE.** This is a real result from a real run, but the
> counterparty is a protocol invented for testing and used by nobody. It is
> **not an external counterparty result**, **not a certification**, and **not
> production**. It is here so you can see the shape of the thing before you ask
> for one.

---

## The question

Two systems each produce their own record of the same eight cases. Do their
results say the same thing? And where they differ, is that a disagreement, a
difference of abstraction, or a place where no mapping exists at all?

## What was examined

A synthetic counterparty protocol and the WEXP reference party, each running
their own code over the same eight frozen cases, pinned to exact commits. Each
side produced its own native result first; only then were the two compared.

## The witness boundary

Each party's result was produced in its own execution domain and recorded before
any comparison. The comparison did not re-run either party — it read what each
had already committed to. Nothing about physical truth was observed by anybody;
what was witnessed is what each system reported, at the point it reported it.

## The scoped finding

**Terminal outcome: `MAPPING_REQUIRED`.**

Across eight cases the relations were not uniform, and that is the finding:

| Relation observed | Cases |
| --- | --- |
| the same proposition supported by both | 2 |
| compatible | 1 |
| different abstraction | 1 |
| genuine disagreement | 1 |
| no mapping present | 1 |
| not comparable | 1 |
| underdetermined | 1 |

Three cases came out `OK`, three `UNDETERMINED`, one `SEMANTIC_DISAGREEMENT`,
one `NOT_DEFINED`.

The record does **not** aggregate these into a score. They are not commensurable
— "these two mean the same thing" and "no mapping exists between these two" are
different facts about the world, and averaging them would destroy both.

## What is *not* established

- Not that either protocol is correct. Neither was judged.
- Not that either system executed anything in the physical world.
- Not that the two systems are compatible in general. Eight frozen cases were
  compared; nothing was established about a ninth.
- Not a certification, and not a badge.
- Not a result that generalizes past the exact pinned inputs it names.

`UNDETERMINED`, `SEMANTIC_DISAGREEMENT` and `no mapping present` are legitimate
observations here, not failures. The run did what it was supposed to do.

## Infrastructure status

`EXECUTED`. The run completed, fetched its pinned inputs, and passed its
publication gate. Had the infrastructure failed, that would have been recorded
as an infrastructure fact and **not** as a result about either party — a broken
procedure is never reported as a semantic outcome.

## Reproducibility

Every input was pinned to an exact commit and every artifact digested. The
semantic projection — the part that must be identical however the run was
orchestrated — is
`bc409c308491de92ffb2f7786c305f6c88c7785b10df9541b82a4b83c7644c5f`, and it has
now come out identical through manual, assisted, automated and hosted paths.

The underlying technical record is the run's own evidence bundle: a semantic
bundle, a comparison summary, an outcome, a claims registry, each party's native
results, and a frozen manifest covering all of it.

---

**The shape to take away:** a WEXP Interop Record says what was asked, what was
looked at, where the evidence was witnessed, what is supported inside that
scope, and what is not established. It does not say "compatible" and it does not
give you a mark out of ten.
