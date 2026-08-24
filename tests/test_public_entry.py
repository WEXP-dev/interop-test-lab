"""Cold-read guards for the public entry point.

Written as tests because a claim about readability that nobody re-checks stops
being true the first time somebody edits the file.

The imagined reader has never read WEXP, has never seen Prototype-000, does not
know our vocabulary, and got only the START-HERE link in an email.
"""

from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
START = (ROOT / "START-HERE.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
ROUTING = (ROOT / "ROUTING.md").read_text(encoding="utf-8")
FORM = (ROOT / ".github" / "ISSUE_TEMPLATE" / "interop-check.yml").read_text(encoding="utf-8")

CTA = "Start an interoperability check"
FIRST_SCREEN_LINES = 25

NEGATIONS = ("not ", "no ", "never", "nothing", "none of")


def plain(text: str) -> str:
    """Markdown emphasis removed and whitespace collapsed.

    "there is **no** compatibility certification" and "there is no compatibility
    certification" are the same sentence to a reader, so they must be the same
    string to a test.
    """
    text = re.sub(r"[*_`]", "", text)
    text = re.sub(r"^\s*>\s?", " ", text, flags=re.M)   # blockquote markers
    text = text.replace("\u2014", "-").replace("\u2013", "-")  # em/en dash
    return " ".join(text.lower().split())


def is_denied(text: str, phrase: str) -> bool:
    """True when every occurrence of `phrase` sits inside a denial.

    A denial is required by the order. A test that cannot tell "WEXP does not
    prove execution" from "WEXP proves execution" would fail the document for
    saying exactly what it was told to say.
    """
    flat = plain(text)
    start = 0
    while True:
        at = flat.find(phrase, start)
        if at == -1:
            return True
        window = flat[max(0, at - 45):at]
        if not any(n in window for n in NEGATIONS):
            return False
        start = at + 1


class ColdRead(unittest.TestCase):

    def test_reader_knows_what_to_do_within_the_first_screen(self):
        first = "\n".join(START.splitlines()[:FIRST_SCREEN_LINES])
        self.assertIn(CTA, first, "the action must be visible without scrolling")
        self.assertIn("issues/new", first, "the action must be a link, not an instruction")

    def test_there_is_exactly_one_primary_action(self):
        """Two calls to action is the same as none."""
        headings = re.findall(r"^#{1,3} .*", START, re.M)
        self.assertNotIn("Choose", " ".join(headings))
        self.assertEqual(START.count("issues/new?template=interop-check.yml"), 2,
                         "one link at the top, one at the end, and no third route")

    def test_all_six_comprehension_questions_are_answerable(self):
        """The six questions a 60-second reader must be able to answer.

        Checked by substance, not by heading text: a reader does not care what
        the sections are called.
        """
        flat = plain(START)
        for question, evidence in (
            ("what problem does this help me investigate",
             "they support something narrower than the claim being made on them"),
            ("why might it matter to me",
             "before someone else does"),
            ("what does wexp not do", "no compatibility certification"),
            ("what could i submit", "any system or specification that produces evidence"),
            ("what may happen after submission", "we first determine which route applies"),
            ("what should i click", "start an interoperability check"),
        ):
            self.assertIn(plain(evidence), flat, f"a reader cannot answer: {question}")

    def test_value_comes_before_process(self):
        """Problem, then value, then action — and all three before terminology."""
        flat = plain(START)
        problem = flat.index("support something narrower")
        value = flat.index("helps you find that boundary")
        action = flat.index("start an interoperability check")
        self.assertLess(problem, value, "the value must follow the problem")
        self.assertLess(value, action, "the action must follow the value")
        for term in ("claim-strength layer", "boundary ceiling", "interop record"):
            self.assertGreater(flat.index(term), action,
                               f"terminology appears before the reader knows why to care: {term}")

    def test_terminology_is_not_a_prerequisite(self):
        before = plain(START.split(CTA)[0])
        for term in ("claim-strength layer", "boundary ceiling", "claim class",
                     "boundary class", "evaluation profile", "interop record",
                     "admission envelope", "prototype-000", "escp"):
            self.assertNotIn(term, before, f"required before the reader can act: {term}")

    def test_github_account_requirement_is_disclosed_before_the_click(self):
        """A newcomer should learn the cost of the click before making it."""
        flat = plain(START)
        first_cta = flat.index("start an interoperability check")
        disclosure = flat.index("submitting the form needs a github account")
        self.assertLess(disclosure - first_cta, 200,
                        "the account requirement must sit with the first call to action")

    def test_automation_is_not_described_as_generally_available(self):
        flat = plain(START)
        self.assertIn("only for classes that have already been explicitly admitted", flat)
        self.assertIn("most new external systems will begin with review or joint research", flat)

    def test_routing_does_not_promise_a_human_per_request(self):
        flat = plain(START)
        self.assertNotIn("someone on the wexp side reads it and routes it", flat)
        self.assertIn("we first determine which route applies", flat)
        self.assertIn("routing is determined from the case itself", flat)

    def test_no_phantom_route_selector_is_described(self):
        """The form has no route selector, so the page must not discuss picking one."""
        self.assertNotIn("picking one in the form does not get it", plain(START))
        form_ids = re.findall(r"id:\s*([a-z_]+)", FORM)
        self.assertNotIn("route", form_ids)

    def test_boundary_ceiling_is_not_stated_absolutely(self):
        """The ceiling is load-bearing, but not a claim about all possible evidence."""
        flat = plain(START)
        self.assertIn("boundary ceiling", flat)
        self.assertNotIn("no matter how much of it there is", flat)
        self.assertIn("more evidence of the same kind, from the same insufficient boundary", flat)

    def test_scope_wording_does_not_promise_universal_execution(self):
        flat = plain(START)
        self.assertNotIn("bring any system that produces a record", flat)
        self.assertIn("whether it can be run automatically depends on the route", flat)

    def test_private_route_is_not_described_as_an_existing_service(self):
        for doc, name in ((START, "START-HERE"), (FORM, "the form")):
            flat = plain(doc)
            self.assertNotIn("we will arrange a private route", flat)
            self.assertNotIn("we will arrange a route first", flat)
            self.assertIn("confirm whether a suitable route is available", flat, name)

    def test_no_response_time_is_promised(self):
        flat = plain(START)
        self.assertNotIn("we respond within", flat)
        self.assertIn("no response-time commitment is offered yet", flat)

    def test_illustrative_example_is_labelled_as_illustrative(self):
        flat = plain(START)
        self.assertIn("illustrative example - not a normative wexp result", flat)

    def test_example_record_is_labelled_synthetic_and_not_certification(self):
        example = (ROOT / "EXAMPLE-INTEROP-RECORD.md").read_text(encoding="utf-8")
        flat = plain(example)
        self.assertIn("synthetic example", flat)
        self.assertIn("not an external counterparty result", flat)
        self.assertIn("not a certification", flat)
        self.assertIn("not production", flat)
        self.assertIn("what is not established", flat)

    def test_example_record_does_not_aggregate_into_a_score(self):
        example = plain((ROOT / "EXAMPLE-INTEROP-RECORD.md").read_text(encoding="utf-8"))
        self.assertIn("does not aggregate these into a score", example)
        self.assertNotIn("compatible: yes", example)

    def test_forbidden_names_appear_nowhere(self):
        for doc in (START, ROUTING, README, FORM,
                    (ROOT / "EXAMPLE-INTEROP-RECORD.md").read_text(encoding="utf-8")):
            for name in ("bradley", "openway", "emilia", "b-01"):
                self.assertNotIn(name, doc.lower())

    def test_mobile_first_contact_avoids_a_wide_table_before_the_value(self):
        """Route descriptions are stacked, not tabled, above the fold."""
        head = "\n".join(START.splitlines()[:60])
        self.assertNotIn("| If | Then |", head)

    def test_prototype_identity_is_not_prominent(self):
        lines = START.splitlines()
        for i, line in enumerate(lines):
            if "Prototype-000" in line:
                self.assertGreater(i, 60, "the prototype name appears too early for a newcomer")

    def test_no_internal_architecture_before_the_action(self):
        before = START.split(CTA)[0]
        for term in ("Prototype-000", "interop_core", "adapter", "workflow_run",
                     "admission envelope", "ledger", "Claim Class", "Boundary Class",
                     "Evaluation Profile", "ESCP"):
            self.assertNotIn(term.lower(), before.lower(),
                             f"internal architecture appears before the action: {term}")

    def test_newcomer_needs_none_of_our_taxonomy(self):
        for term in ("Claim Class", "Boundary Class", "Evaluation Profile", "ESCP",
                     "Admission Envelope", "admission ticket"):
            self.assertNotIn(term.lower(), FORM.lower(),
                             f"the intake form demands internal vocabulary: {term}")

    def test_canon_language_is_present_and_exact(self):
        self.assertIn("claim-strength layer for digital execution evidence", START)
        self.assertIn("how strong a claim execution evidence can support", START)
        self.assertIn("without either side giving up authority over its own semantics", START)

    def test_boundary_ceiling_survives_the_simplification(self):
        self.assertIn("Boundary Ceiling", START)

    def test_forbidden_claims_appear_nowhere_on_the_public_surface(self):
        forbidden = [
            "what your evidence proves",
            "wexp proves execution",
            "compatibility certified",
            "universally interoperable",
            "production-ready",
            "production ready",
            "validates another specification as correct",
        ]
        for doc, name in ((START, "START-HERE.md"), (ROUTING, "ROUTING.md"), (FORM, "the intake form")):
            for phrase in forbidden:
                self.assertTrue(
                    is_denied(doc, plain(phrase)),
                    f"{name} asserts a forbidden claim rather than denying it: {phrase}")

    def test_the_things_wexp_does_not_claim_are_stated_not_implied(self):
        for phrase in ("does not tell you what your evidence proves",
                       "does not prove that execution happened",
                       "no compatibility certification",
                       "none of this is production-ready"):
            self.assertIn(plain(phrase), plain(START), f"missing an explicit denial: {phrase}")

    def test_semantic_firewall_is_stated_plainly(self):
        self.assertIn("does not automatically change WEXP", START)
        self.assertIn("Repetition does not ratify semantics", START)
        self.assertIn("Neither does commercial interest", START)
        self.assertIn("Operational repetition does not ratify semantics", ROUTING)

    def test_a_weaker_result_is_described_as_success(self):
        self.assertIn("successful result", START)
        self.assertIn("successful result", ROUTING)

    def test_privacy_warning_precedes_any_request_for_material(self):
        warning = FORM.lower().index("do not paste secrets")
        first_field = FORM.lower().index("what is your system")
        self.assertLess(warning, first_field, "the privacy warning must come first")

    def test_intake_never_asks_for_private_material(self):
        for term in ("private key", "credential", "token", "password", "secret value"):
            self.assertNotIn(f"label: {term}", FORM.lower())
        self.assertIn("we will first confirm whether a suitable route is available", plain(FORM))

    def test_readme_points_a_newcomer_out_before_the_engine_room(self):
        head = "\n".join(README.splitlines()[:6])
        self.assertIn("Start here", head)
        self.assertIn("START-HERE.md", head)

    def test_no_tracking(self):
        for doc in (START, ROUTING, README, FORM):
            for term in ("google-analytics", "utm_source", "plausible.io"):
                self.assertNotIn(term, doc.lower())
            # "No tracking pixels." is a promise, not a pixel.
            self.assertTrue(is_denied(doc, "tracking pixel"))

    def test_unobservable_funnel_states_are_disclaimed_not_claimed(self):
        self.assertIn("ENTRY_VIEWABLE", ROUTING)
        self.assertIn("INTAKE_STARTED", ROUTING)
        self.assertIn("not** honestly observable", ROUTING)


if __name__ == "__main__":
    unittest.main()
