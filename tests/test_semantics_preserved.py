"""The experiment's meaning is not allowed to move because its topology did.

Everything asserted here was true before this security work and must still be
true after it. A hardening change that quietly turns a legitimate semantic
result into an infrastructure failure has broken the experiment, not secured it.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from support import REPO_ROOT

EXPERIMENT = REPO_ROOT / "experiments" / "X-001"
HOSTED = REPO_ROOT / ".github" / "workflows" / "interop-hosted.yml"

#: Every terminal outcome the charter admits. Non-success outcomes are results.
PERMITTED_TERMINAL_OUTCOMES = {
    "REPRODUCED", "BOUNDARY_IDENTIFIED", "MAPPING_REQUIRED",
    "SEMANTIC_DISAGREEMENT", "EXPECTATION_MISMATCH", "IMPLEMENTATION_LIMIT",
    "COUNTERPARTY_INCOMPLETE", "UNILATERAL_REVIEW", "REVIEW_REQUIRED",
}

REQUIRED_PHASES = [
    "INIT", "PARTIES_DECLARED", "AUTHORITIES_PINNED", "CAPABILITIES_DECLARED",
    "CASES_FROZEN", "EXPECTATIONS_COMMITTED", "EXPECTATIONS_REVEALED",
    "EXECUTION_ALLOWED", "EXECUTED", "COMPARED", "REVIEW_READY",
]


def load(name: str) -> object:
    return json.loads((EXPERIMENT / f"{name}.json").read_text(encoding="utf-8"))


class CharterUnchangedTest(unittest.TestCase):
    def test_every_terminal_outcome_remains_permitted(self) -> None:
        """TEST 7: hardening removed no legitimate terminal outcome."""
        policy = load("policy")
        self.assertEqual(set(policy["permitted_terminal_outcomes"]),
                         PERMITTED_TERMINAL_OUTCOMES)

    def test_the_phase_sequence_is_unchanged(self) -> None:
        self.assertEqual(load("policy")["required_phases"], REQUIRED_PHASES)

    def test_the_stance_maps_are_unchanged(self) -> None:
        stance = load("policy")["comparison_policy"]["stance_maps"]
        self.assertEqual(stance["GLYPHLOCK"]["supports_values"], ["GLYPH_SEALED"])
        self.assertEqual(stance["GLYPHLOCK"]["denies_values"],
                         ["GLYPH_BROKEN", "GLYPH_REFUSED"])
        self.assertEqual(stance["GLYPHLOCK"]["undetermined_values"], ["GLYPH_PARTIAL"])
        self.assertEqual(stance["GLYPHLOCK"]["not_expressible_values"],
                         ["GLYPH_NO_ANALOGUE"])
        self.assertEqual(stance["WEXP"]["supports_values"], ["VERIFIED"])
        self.assertEqual(stance["WEXP"]["denies_values"], ["COMMITMENT_MISMATCH"])

    def test_the_missing_mapping_case_is_still_declared(self) -> None:
        self.assertEqual(
            load("policy")["comparison_policy"]["mapping_absent_cases"], ["X-C-008"])

    def test_the_frozen_case_set_is_unchanged_in_size_and_identity(self) -> None:
        cases = load("cases")
        self.assertEqual(cases["case_set_id"], "X-001-CASES")
        self.assertEqual([case["case_id"] for case in cases["cases"]],
                         [f"X-C-{index:03d}" for index in range(1, 9)])

    def test_the_prohibited_claim_is_still_prohibited(self) -> None:
        claims = {claim["claim_id"]: claim for claim in load("claims")}
        self.assertEqual(claims["X-CL-003"]["status"], "PROHIBITED")
        self.assertTrue(claims["X-CL-003"]["prohibited_in_publication"])
        self.assertEqual(claims["X-CL-002"]["status"], "UNDERDETERMINED")

    def test_the_independence_non_claim_is_still_stated(self) -> None:
        """The framework has never claimed OS-level information control."""
        self.assertIn(
            "Prototype-000 performs no operating-system-level information control.",
            load("policy")["independence_policy"]["non_claims"])


class InfrastructureIsNotASemanticResultTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = HOSTED.read_text(encoding="utf-8")

    def test_the_unavailable_path_states_it_is_not_a_failure(self) -> None:
        """TEST 6: no semantic conclusion is drawn from a run that could not run."""
        self.assertIn('"status": "INFRASTRUCTURE EXECUTION UNAVAILABLE"', self.text)
        self.assertIn('"is_experiment_failure": false', self.text)
        self.assertIn('"is_portability_failure": false', self.text)
        self.assertIn("No semantic conclusion may be drawn from this run.", self.text)

    def test_the_unavailable_path_is_reachable_without_credentials(self) -> None:
        self.assertIn("steps.pin.outputs.available != 'true'", self.text)
        self.assertIn("steps.app.outputs.available != 'true'", self.text)

    def test_the_unavailable_record_is_an_allowlisted_artifact(self) -> None:
        allowlist = json.loads(
            (REPO_ROOT / "publication" / "ALLOWLIST.json").read_text(encoding="utf-8"))
        self.assertIn("HOSTED-RESULT.json",
                      {entry["path"] for entry in allowlist["admitted"]})


if __name__ == "__main__":
    unittest.main()
