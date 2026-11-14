# Bring an implementation

If you have written your own implementation of the appraisal procedure of
[draft-sergeev-wexp-core-02](https://datatracker.ietf.org/doc/draft-sergeev-wexp-core/02/),
it can be run here on the public corpus: 124 normalized inputs with frozen
expected results, in two sets of
[WEXP-dev/wexp-vectors](https://github.com/WEXP-dev/wexp-vectors).

This is the more valuable kind of check. The two appraisers this project has
were both written under one operator, so their agreement shows less than the
agreement of an implementation written by somebody else from the text alone.

## What you need

A public repository, and a command that takes one input and prints one result:

    <your command> --input <normalized-input.json> --profiles <profiles.json>

The result is a single JSON object on standard output with the twenty
components of section 8.5. The JSON representation of inputs and results is the
local one described in
[`docs/REPRESENTATION.md` of wexp-check](https://github.com/WEXP-dev/wexp-check/blob/main/docs/REPRESENTATION.md);
it is a harness, not a standardized carrier.

A case counts only when the command ends with exit status 0 and prints one JSON
object of at most 1 MiB with no repeated key. Every component is present: a
component that is absent is reported as absent and is not read as `null`.

Any language works. If your code needs a build step, say what the command is.

## How to ask

[Start an interoperability check](START-HERE.md) and say that you are bringing
an implementation. Give the repository, the commit, and the command.

## What happens

A maintainer starts the run. Your code is checked out at the exact commit in a
job that holds no secret and nothing private, and is started once per case with
a time limit. A separate job, which never checks out or runs your code, compares
what it printed with the frozen expectations, component by component, and writes
a summary: how many cases are equal, and for the rest which components differ.

The separation of jobs is the only isolation relied on. The exit status and the
printed bytes of each case are recorded in the job where your code runs, so the
comparison rests on that job having recorded them as they were.

You can also do all of this yourself first: the corpus and the expectations are
public, and [`tools/appraiser_run.py`](tools/appraiser_run.py) is the same
script the run uses.

## What the result says, and what it does not

It says what your implementation returned on these inputs in one run. A
difference is a finding to look at together: it may be about your code, or about
a place where the text allows two readings, and the second kind is input to the
next revision of the draft.

The corpus does not claim to be a complete test suite, so equality on every case
is not a statement about your implementation beyond these cases, and nothing
here certifies anything. The expectations are public; that an implementation was
written without reading them is a declaration by its author, which a run cannot
check.

Nothing is published automatically. If a result is recorded, its wording and
whether to name you are agreed with you first.
