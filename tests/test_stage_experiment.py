"""Only declared experiment inputs cross into the tooling checkout.

Write access to this public repository is still write access. What it must not
be is a way to place code inside a private checkout and have that code run with
the credential in scope.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from support import REPO_ROOT

from stage_experiment import DECLARED_INPUTS, StagingRefused, stage

EXPERIMENT = REPO_ROOT / "experiments" / "X-001"


class StageExperimentTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.experiment = self.root / "experiments" / "X-001"
        shutil.copytree(EXPERIMENT, self.experiment)
        self.into = self.root / "tooling" / "interop" / "experiments" / "X-001"

    def test_the_real_experiment_stages(self) -> None:
        report = stage(self.experiment, self.into)
        self.assertEqual(report["status"], "STAGED")
        self.assertEqual(sorted(report["staged"]), sorted(DECLARED_INPUTS))
        self.assertEqual(sorted(p.name for p in self.into.iterdir()),
                         sorted(DECLARED_INPUTS))

    def test_a_planted_module_does_not_cross(self) -> None:
        """The escalation this closes: code into a checkout this repo does not own."""
        (self.experiment / "run.py").write_text("import os\n", encoding="utf-8")
        with self.assertRaises(StagingRefused) as raised:
            stage(self.experiment, self.into)
        self.assertIn("run.py", str(raised.exception))
        self.assertFalse(self.into.exists())

    def test_a_planted_package_does_not_cross(self) -> None:
        (self.experiment / "interop_core").mkdir()
        (self.experiment / "interop_core" / "__init__.py").write_text("", encoding="utf-8")
        with self.assertRaises(StagingRefused) as raised:
            stage(self.experiment, self.into)
        self.assertIn("no subdirectories", str(raised.exception))

    def test_a_symlink_does_not_cross(self) -> None:
        (self.experiment / "escape.json").symlink_to(self.root / "elsewhere.json")
        with self.assertRaises(StagingRefused) as raised:
            stage(self.experiment, self.into)
        self.assertIn("symlink", str(raised.exception))

    def test_a_non_json_input_is_refused(self) -> None:
        (self.experiment / "policy.json").write_text("not json", encoding="utf-8")
        with self.assertRaises(StagingRefused) as raised:
            stage(self.experiment, self.into)
        self.assertIn("policy.json", str(raised.exception))

    def test_an_incomplete_experiment_is_refused(self) -> None:
        (self.experiment / "claims.json").unlink()
        with self.assertRaises(StagingRefused) as raised:
            stage(self.experiment, self.into)
        self.assertIn("incomplete", str(raised.exception))

    def test_the_declared_list_matches_the_repository(self) -> None:
        self.assertEqual(sorted(p.name for p in EXPERIMENT.iterdir()),
                         sorted(DECLARED_INPUTS))


if __name__ == "__main__":
    unittest.main()
