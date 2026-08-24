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
    return " ".join(re.sub(r"[*_`]", "", text).lower().split())


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

    def test_all_six_required_questions_are_answered(self):
        for heading in ("What is this?",
                        "What can I test?",
                        "What do I need to provide?",
                        "What happens after I submit?",
                        "What does WEXP NOT claim?",
                        "How do I start?"):
            self.assertIn(heading, START, f"START-HERE must answer: {heading}")

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
        self.assertIn("we will arrange a route first", FORM.lower())

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
