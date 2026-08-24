"""The three required route cases, run against the published rubric.

These are the cases the entry point promises to handle. They run in CI so the
promise stays true rather than staying written down.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "selfservice"))

import routing  # noqa: E402


class RouteCases(unittest.TestCase):

    def test_known_class_public_and_complete_is_self_service(self):
        """A routine case with nothing missing runs automatically."""
        case = {
            "existing_mapping_known": True,
            "public_source": True,
            "exact_revision": True,
            "self_contained": True,
            "public_example_material": True,
        }
        result = routing.route(case)
        self.assertEqual(result["route"], routing.SELF_SERVICE)
        self.assertEqual(result["external_wording"], "Run it automatically.")

    def test_specification_author_asking_whether_their_records_support_a_claim(self):
        """A public standards author whose record model has no established mapping.

        The mapping IS the question, so it is research. Running it automatically
        would answer a question nobody has posed properly yet.
        """
        case = {
            "public_source": True,
            "exact_revision": True,
            "self_contained": True,
            "public_example_material": True,
            "existing_mapping_known": False,
            "semantic_mapping_is_the_question": True,
        }
        result = routing.route(case)
        self.assertEqual(result["route"], routing.JOINT_RESEARCH)
        self.assertIn("no established mapping", result["reason"])

    def test_known_semantics_with_private_evidence_is_assisted(self):
        """Known semantics, unsupported operational condition. Reviewed, not researched."""
        case = {
            "existing_mapping_known": True,
            "public_source": False,
            "requires_private_material": True,
        }
        result = routing.route(case)
        self.assertEqual(result["route"], routing.ASSISTED_REVIEW)

    def test_special_disclosure_conditions_are_assisted(self):
        case = {"existing_mapping_known": True, "special_disclosure_conditions": True}
        self.assertEqual(routing.route(case)["route"], routing.ASSISTED_REVIEW)

    def test_privacy_is_decided_before_novelty(self):
        """A private case that is also novel must still be reviewed, not researched.

        Otherwise the private material would be discussed in a research thread
        before anyone decided it was safe to send.
        """
        case = {"requires_private_material": True, "semantic_mapping_is_the_question": True}
        self.assertEqual(routing.route(case)["route"], routing.ASSISTED_REVIEW)

    def test_known_semantics_missing_only_an_exact_revision_is_assisted_not_research(self):
        """An operational gap is not a scientific question."""
        case = {
            "existing_mapping_known": True,
            "public_source": True,
            "exact_revision": False,
            "self_contained": True,
            "public_example_material": True,
        }
        result = routing.route(case)
        self.assertEqual(result["route"], routing.ASSISTED_REVIEW)
        self.assertIn("exact_revision", result["reason"])

    def test_non_self_service_cases_are_not_all_routed_to_research(self):
        cases = [
            {"existing_mapping_known": True, "requires_private_material": True},
            {"existing_mapping_known": True, "public_source": True, "exact_revision": True,
             "self_contained": False, "public_example_material": True},
        ]
        for case in cases:
            self.assertEqual(routing.route(case)["route"], routing.ASSISTED_REVIEW)

    def test_route_never_reads_a_requested_route_field(self):
        """The guarantee is structural: the field is not consulted at all."""
        import ast
        source = (ROOT / "selfservice" / "routing.py").read_text()
        self.assertNotIn("submitter_requested_route", ast.unparse(ast.parse(source)))

    def test_submitter_cannot_choose_their_own_route(self):
        """A submitter asking for SELF_SERVICE does not get it by asking."""
        case = {
            "existing_mapping_known": False,
            "semantic_mapping_is_the_question": True,
            "submitter_requested_route": routing.SELF_SERVICE,
            "public_source": True, "exact_revision": True,
            "self_contained": True, "public_example_material": True,
        }
        self.assertEqual(routing.route(case)["route"], routing.JOINT_RESEARCH)

    def test_every_route_has_plain_external_wording(self):
        for name in routing.ROUTES:
            self.assertIn(name, routing.EXTERNAL_WORDING)
            self.assertTrue(routing.EXTERNAL_WORDING[name].endswith("."))

    def test_rubric_uses_no_internal_taxonomy(self):
        """A newcomer supplies none of our vocabulary, so none may appear here."""
        import ast
        tree = ast.parse((ROOT / "selfservice" / "routing.py").read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)):
                if (node.body and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)):
                    node.body.pop(0)          # prose may name what the logic must not use
        logic = ast.unparse(tree)
        for term in ("Claim Class", "Boundary Class", "Evaluation Profile",
                     "ESCP", "admission_envelope", "envelope_id"):
            self.assertNotIn(term, logic, f"internal taxonomy leaked into the rubric: {term}")


if __name__ == "__main__":
    unittest.main()
