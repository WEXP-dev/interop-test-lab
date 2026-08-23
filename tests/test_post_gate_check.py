"""Nothing may change between the disclosure gate and the upload."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import minimal_allowlist, write_json

from staging import GateFailure
import post_gate_check
import publication_gate


class PostGateImmutabilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.staging = Path(self._tmp.name) / "evidence"
        self.staging.mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)
        write_json(self.staging / "outcome.json", {"reported_outcome": "MAPPING_REQUIRED"})
        publication_gate.gate(self.staging, minimal_allowlist(["outcome.json"]),
                              experiment_id="T-000")

    def test_an_unchanged_tree_verifies(self) -> None:
        report = post_gate_check.verify(self.staging)
        self.assertEqual(report["status"], "UNCHANGED")
        self.assertEqual(report["entries_verified"], 1)

    def test_a_mutated_artifact_is_detected(self) -> None:
        """TEST 3: post-scan tampering cannot reach the upload."""
        (self.staging / "outcome.json").write_text('{"reported_outcome":"REPRODUCED"}\n',
                                                   encoding="utf-8")
        with self.assertRaises(GateFailure) as raised:
            post_gate_check.verify(self.staging)
        self.assertIn("mutated after the disclosure gate", str(raised.exception))

    def test_an_injected_artifact_is_detected(self) -> None:
        write_json(self.staging / "HOSTILE-EXTRA.json", {"note": "injected"})
        with self.assertRaises(GateFailure) as raised:
            post_gate_check.verify(self.staging)
        self.assertIn("appeared after the disclosure gate", str(raised.exception))

    def test_a_removed_artifact_is_detected(self) -> None:
        (self.staging / "outcome.json").unlink()
        with self.assertRaises(GateFailure) as raised:
            post_gate_check.verify(self.staging)
        self.assertIn("vanished after the disclosure gate", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
