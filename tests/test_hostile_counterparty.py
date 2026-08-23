"""A hostile counterparty, run the way a real one would be run.

Two topologies are exercised with the same hostile participant:

* the **remediated** one, where the participant's job holds no private checkout,
  no credential material and no staging tree;
* a **co-located** control, which reproduces the defect this work removed.

The control is not decoration. Without it, six REFUSED verdicts prove only that
the test could not find anything — which is also what a broken test looks like.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support import REPO_ROOT, new_sentinel

HOSTILE = REPO_ROOT / "tools" / "hostile_party.py"


class HostileParticipantTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.sentinel_value = new_sentinel()
        self.sentinel_name = "PRIVATE-BOUNDARY-MARKER.txt"

    def build_private_domain(self) -> Path:
        """A stand-in for the coordination domain: private tooling and a marker."""
        private = self.root / "coordination" / "tooling" / "interop"
        private.mkdir(parents=True)
        (private / self.sentinel_name).write_text(self.sentinel_value + "\n", encoding="utf-8")
        (private / "interop_core.py").write_text("# private tooling\n", encoding="utf-8")
        staging = self.root / "coordination" / "build" / "evidence"
        staging.mkdir(parents=True)
        (staging / "outcome.json").write_text('{"reported_outcome":"MAPPING_REQUIRED"}\n',
                                              encoding="utf-8")
        return private

    def run_hostile(self, workspace: Path, *, env_extra: dict[str, str] | None = None) -> dict:
        workspace.mkdir(parents=True, exist_ok=True)
        request = workspace / "request.wire"
        request.write_text("GLYPHLOCK/1\nwarden: north-gate\n", encoding="utf-8")
        report = workspace / "hostile-report.json"

        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(workspace),
            "WEXP_TEST_SENTINEL_BASENAME": self.sentinel_name,
            "WEXP_HOSTILE_REPORT": str(report),
        }
        env.update(env_extra or {})

        completed = subprocess.run(
            [sys.executable, str(HOSTILE), str(request)],
            cwd=workspace, env=env, capture_output=True, text=True,
            timeout=120, check=False,
        )
        self.stdout = completed.stdout
        return json.loads(report.read_text(encoding="utf-8"))

    def outcomes(self, report: dict) -> dict[str, str]:
        return {attempt["attempt"]: attempt["outcome"] for attempt in report["attempts"]}

    # ------------------------------------------------------------------
    # The remediated topology.
    #
    # The counterparty job never checks out the private tooling and never holds
    # a staging tree, so in its domain that material is not merely unreadable —
    # it is not there. That is what job separation buys, and the fixture models
    # it by not creating it. The control below is what makes the absence mean
    # something: the same probe, given the co-located layout, finds everything.
    # ------------------------------------------------------------------

    def test_the_isolated_party_domain_refuses_every_attempt(self) -> None:
        """TEST 2: the hostile participant reaches no private material."""
        party_domain = self.root / "party-domain" / "work"

        report = self.run_hostile(party_domain)
        outcomes = self.outcomes(report)

        self.assertEqual(outcomes["A"], "REFUSED", "read a private marker")
        self.assertEqual(outcomes["B"], "REFUSED", "enumerated a private checkout")
        self.assertEqual(outcomes["C"], "REFUSED", "read out-of-contract environment")
        self.assertEqual(outcomes["D"], "REFUSED", "emitted into publication staging")
        self.assertEqual(outcomes["E"], "REFUSED", "mutated a staged artifact")
        self.assertEqual(outcomes["F"], "REFUSED", "printed a protected marker")
        self.assertNotIn(self.sentinel_value, self.stdout)
        self.assertNotIn(self.sentinel_value, json.dumps(report))

    def test_the_isolated_party_domain_still_produces_a_party_result(self) -> None:
        """Isolation must not stop a counterparty from being a counterparty."""
        self.run_hostile(self.root / "party-domain" / "work")
        self.assertIn("GLYPHLOCK-RESULT/1", self.stdout)

    def test_credential_material_is_absent_from_the_party_domain(self) -> None:
        report = self.run_hostile(self.root / "party-domain" / "work")
        attempt_c = next(a for a in report["attempts"] if a["attempt"] == "C")
        self.assertEqual(attempt_c["visible"], [])

    def test_the_workflow_gives_the_counterparty_job_nothing_to_find(self) -> None:
        """The fixture's premise, checked against the workflow rather than assumed."""
        workflow = (REPO_ROOT / ".github" / "workflows"
                    / "interop-hosted.yml").read_text(encoding="utf-8")
        counterparty = workflow.split("coordinate:")[0]
        self.assertNotIn("secrets.", counterparty)
        self.assertNotIn("wexp-work", counterparty)
        self.assertNotIn("build/evidence", counterparty)

    # ------------------------------------------------------------------
    # The control: the topology this work removed.
    # ------------------------------------------------------------------

    def test_the_co_located_control_is_breached(self) -> None:
        """The defect, reproduced, so the passing case above means something."""
        private = self.build_private_domain()
        co_located = private.parent.parent / "work"

        report = self.run_hostile(
            co_located, env_extra={"WEXP_WORK_PIN": "a" * 40})
        outcomes = self.outcomes(report)

        self.assertEqual(outcomes["A"], "SUCCEEDED",
                         "the control must reach the private marker")
        self.assertEqual(outcomes["B"], "SUCCEEDED")
        self.assertEqual(outcomes["C"], "SUCCEEDED")
        self.assertEqual(outcomes["D"], "SUCCEEDED")
        self.assertEqual(outcomes["E"], "SUCCEEDED")
        self.assertEqual(outcomes["F"], "SUCCEEDED")


if __name__ == "__main__":
    unittest.main()
