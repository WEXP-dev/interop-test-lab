"""The publication gate admits by exact path or it refuses."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from support import minimal_allowlist, write_json

from staging import GateFailure, MANIFEST_NAME, load_manifest
import publication_gate


class PublicationGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.staging = self.root / "evidence"
        self.staging.mkdir()
        self.addCleanup(self._tmp.cleanup)

    def stage(self, name: str, payload: object = None) -> Path:
        return write_json(self.staging / name, payload if payload is not None else {"ok": True})

    def test_declared_tree_is_admitted_and_manifested(self) -> None:
        self.stage("outcome.json")
        self.stage("native/wexp/RESULTS.json")
        allowlist = minimal_allowlist(["outcome.json", "native/wexp/RESULTS.json"])

        report = publication_gate.gate(self.staging, allowlist, experiment_id="T-000")

        self.assertEqual(report["status"], "ADMITTED")
        self.assertEqual(report["admitted_entries"], 2)
        manifest = load_manifest(self.staging / MANIFEST_NAME)
        self.assertEqual({e["path"] for e in manifest["entries"]},
                         {"outcome.json", "native/wexp/RESULTS.json"})

    def test_an_undeclared_file_fails_closed(self) -> None:
        """TEST 4: an unexpected publication file is refused, not shrugged at."""
        self.stage("outcome.json")
        self.stage("HOSTILE-EXTRA.json")
        allowlist = minimal_allowlist(["outcome.json"])

        with self.assertRaises(GateFailure) as raised:
            publication_gate.gate(self.staging, allowlist, experiment_id="T-000")
        self.assertIn("HOSTILE-EXTRA.json", str(raised.exception))
        self.assertFalse((self.staging / MANIFEST_NAME).exists())

    def test_a_declared_but_absent_file_is_reported_not_fatal(self) -> None:
        """A party that did not run is a legitimate state."""
        self.stage("outcome.json")
        allowlist = minimal_allowlist(["outcome.json", "native/glyphlock/RESULTS.json"])

        report = publication_gate.gate(self.staging, allowlist, experiment_id="T-000")

        self.assertEqual(report["status"], "ADMITTED")
        self.assertEqual(report["declared_but_absent"], ["native/glyphlock/RESULTS.json"])

    def test_wildcards_are_refused(self) -> None:
        """A wildcard is how an unrevealed blind fixture reaches a bundle."""
        self.stage("blind/B-01.json")
        allowlist = minimal_allowlist(["blind/*.json"])

        with self.assertRaises(GateFailure) as raised:
            publication_gate.gate(self.staging, allowlist, experiment_id="T-000")
        self.assertIn("wildcards are refused", str(raised.exception))

    def test_an_unrevealed_blind_fixture_is_not_admitted(self) -> None:
        """§17 G: blind bytes are not in the allowlist, so they cannot ship."""
        self.stage("outcome.json")
        self.stage("blind/B-01-unrevealed.json", {"bytes": "not yet revealed"})
        allowlist = minimal_allowlist(["outcome.json"])

        with self.assertRaises(GateFailure) as raised:
            publication_gate.gate(self.staging, allowlist, experiment_id="T-000")
        self.assertIn("blind/B-01-unrevealed.json", str(raised.exception))

    def test_a_symlink_is_refused(self) -> None:
        self.stage("outcome.json")
        (self.staging / "escape.json").symlink_to(self.root / "outside.json")
        allowlist = minimal_allowlist(["outcome.json", "escape.json"])

        with self.assertRaises(GateFailure) as raised:
            publication_gate.gate(self.staging, allowlist, experiment_id="T-000")
        self.assertIn("symlink", str(raised.exception))

    def test_the_repository_allowlist_is_wildcard_free_and_exact(self) -> None:
        allowlist = json.loads(
            (Path(publication_gate.__file__).resolve().parents[1]
             / "publication" / "ALLOWLIST.json").read_text(encoding="utf-8"))
        paths = publication_gate.admitted_paths(allowlist)
        self.assertIn("semantic-bundle.json", paths)
        self.assertTrue(all("*" not in path for path in paths))


if __name__ == "__main__":
    unittest.main()
