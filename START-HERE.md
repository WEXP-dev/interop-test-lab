# Want to test your system with WEXP? Start here.

**→ [Start an interoperability check](https://github.com/WEXP-dev/interop-test-lab/issues/new?template=interop-check.yml)**

That link is the whole thing. Fill in what you know, in your own words. You do
not need to read anything else on this page first, and you do not need to
understand how WEXP works internally to ask the question.

---

## 1. What is this?

WEXP is a **claim-strength layer for digital execution evidence**. It helps
determine *how strong a claim execution evidence can support, given where and
how it was witnessed*.

WEXP Interop examines whether evidence from another system can support a bounded
WEXP claim **without either side giving up authority over its own semantics**.
Your specification stays yours. Ours stays ours. The question is what, if
anything, can be said across the gap.

## 2. What can I test?

Bring any system that produces a record of something happening — a receipt, an
attestation, a log entry, an audit record, an observation, a signed result.

The question we can help you answer is: *given this evidence, what claim can be
supported, and where does that claim have to stop?*

That last part is not a formality. Every claim has a **Boundary Ceiling**: the
strongest thing the evidence can support, past which it cannot go no matter how
much of it there is. Finding out where your ceiling sits is usually the useful
result.

## 3. What do I need to provide?

Only what you already have:

- what your system, specification or project is called;
- a public repository or authoritative source, if there is one;
- the exact revision or commit, if you know it;
- what evidence, record or result it produces;
- what question you want answered;
- what claim you think that evidence supports — if you have a view;
- a public example or test file, if you can share one;
- anything you are unsure about.

**Do not send secrets, credentials, private keys, tokens, or confidential
material.** If your case needs any of those, say so in the form and we will
arrange a private route *before* anything private is sent.

## 4. What happens after I submit?

Someone on the WEXP side reads it and routes it. There are three routes, and
the honest description of each is one sentence:

| If | Then |
| --- | --- |
| your case matches something already worked out | **Run it automatically.** |
| the semantics are understood but your operating conditions are unusual | **Review it with us.** |
| the mapping from your evidence to a WEXP claim is itself the open question | **Research it with us.** |

You do not pick your route, and picking one in the form does not get it. That is
not gatekeeping — it is because the third case is genuinely a research question,
and answering it automatically would answer a question nobody had posed properly.

The routing rubric is public: [`ROUTING.md`](ROUTING.md).

You get an **Interop Record**: a scoped, written result. Possible outcomes
include supported within a stated scope, supported with qualifiers,
underdetermined, mapping required, semantic disagreement, out of scope, or
infrastructure unavailable.

**A refusal or a weaker claim is a successful result.** If the honest answer is
"this evidence supports less than you hoped", that is the answer, and it is worth
more than a generous one.

## 5. What does WEXP NOT claim?

Plainly, because these are the things people expect and we do not do:

- WEXP does **not** tell you what your evidence proves.
- WEXP does **not** prove that execution happened.
- There is **no** compatibility certification, and **no** badge.
- Nothing here is **universally interoperable**, and no result generalizes past
  the scope it names.
- None of this is **production-ready**. It is an experimental prototype.
- WEXP does **not** validate another specification as correct. Your semantics
  are not on trial.

An Interop Record describes one bounded exercise. It is not a verdict about your
system.

### One more thing, and it matters

**A new interop finding does not automatically change WEXP.** If your case looks
like it exposes new semantics, it stops for review and adjudication rather than
being guessed at or quietly adopted.

Repetition does not ratify semantics. Neither does commercial interest. If we
run your case a hundred times, that makes it well-tested, not settled.

## 6. How do I start?

**→ [Start an interoperability check](https://github.com/WEXP-dev/interop-test-lab/issues/new?template=interop-check.yml)**

If you would rather just ask a question first, open the same form and say so in
the last field. That is a fine way to use it.

---

*Prototype-000 is an experimental, disposable architectural prototype. It is not
production tooling and carries no security certification. If you want the
internals, they start at [`README.md`](README.md) — but you do not need them to
ask a question.*
