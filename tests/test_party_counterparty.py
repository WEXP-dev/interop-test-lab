"""The counterparty, run in its own domain, still produces the same result.

Security work that changes what the exercise observes is not security work. The
counterparty's native results are the input to every comparison downstream, so
they are the thing to hold fixed: this checks the isolated party domain against
the frozen expectations the experiment already committed to.

The counterparty's own repository is required. It is a public, pinned checkout;
CI supplies it, and a developer can supply it with WEXP_SUBJECT_ROOT.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support import REPO_ROOT

from staging import canonical_sha256

HARNESS = REPO_ROOT / "tools" / "party_counterparty.py"
CASES = REPO_ROOT / "experiments" / "X-001" / "cases.json"
EXPECTATIONS = REPO_ROOT / "experiments" / "X-001" / "expectations.json"


def subject_root() -> Path | None:
    for candidate in (os.environ.get("WEXP_SUBJECT_ROOT"), REPO_ROOT / "subject",
                      REPO_ROOT.parent / "interop-test-subject"):
        if candidate and (Path(candidate) / "glyphlock" / "runner.py").is_file():
            return Path(candidate)
    return None


@unittest.skipUnless(subject_root(), "the pinned counterparty checkout is not present")
class PartyDomainTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        completed = subprocess.run(
            [sys.executable, str(HARNESS),
             "--cases", str(CASES),
             "--runner", str(subject_root() / "glyphlock" / "runner.py"),
             "--workspace", str(root / "work"),
             "--output", str(root / "native"),
             "--party-id", "GLYPHLOCK",
             "--source-repository", "WEXP-dev/interop-test-subject",
             "--source-commit", "0" * 40],
            capture_output=True, text=True, timeout=300, check=False,
        )
        assert completed.returncode == 0, completed.stderr
        cls.results = json.loads((root / "native" / "RESULTS.json").read_text(encoding="utf-8"))
        cls.domain = json.loads((root / "native" / "PARTY-DOMAIN.json").read_text(encoding="utf-8"))
        cls.expectations = json.loads(EXPECTATIONS.read_text(encoding="utf-8"))["GLYPHLOCK"]

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def by_case(self) -> dict[str, dict]:
        return {entry["case_id"]: entry for entry in self.results["results"]}

    def test_every_frozen_case_was_executed(self) -> None:
        self.assertEqual(set(self.by_case()), set(self.expectations))

    def test_the_isolated_domain_reproduces_every_frozen_expectation(self) -> None:
        """TEST 1: the semantic projection is unchanged by the topology change."""
        for case_id, expected in sorted(self.expectations.items()):
            with self.subTest(case=case_id):
                self.assertEqual(self.by_case()[case_id]["native_result"], expected)

    def test_native_result_identities_match_the_framework_convention(self) -> None:
        """The digest a party domain computes is the digest the run records."""
        for case_id, expected in sorted(self.expectations.items()):
            with self.subTest(case=case_id):
                self.assertEqual(
                    canonical_sha256(self.by_case()[case_id]["native_result"]),
                    canonical_sha256(expected),
                )

    def test_a_case_the_counterparty_cannot_execute_is_not_a_failure(self) -> None:
        """TEST 7: an unsupported revision stays a recorded non-failure state."""
        entry = self.by_case()["X-C-007"]
        self.assertEqual(entry["execution_status"], "NOT_IMPLEMENTED")
        self.assertIsNone(entry["native_result"])
        self.assertIsNone(self.expectations["X-C-007"])

    def test_the_no_analogue_state_survives_the_boundary(self) -> None:
        """The state no counterparty can mirror is the one worth not losing."""
        self.assertEqual(self.by_case()["X-C-005"]["native_result"]["seal-state"],
                         "GLYPH_NO_ANALOGUE")

    def test_the_party_domain_record_declares_its_isolation(self) -> None:
        self.assertEqual(self.domain["isolation"], {
            "private_wexp_source_present": False,
            "credential_material_present": False,
            "publication_staging_present": False,
        })


@unittest.skipUnless(subject_root(), "the pinned counterparty checkout is not present")
class RelativeWorkspaceTest(unittest.TestCase):
    """HL-001: the workflow passes a relative --workspace, and once did not work.

    The harness sets the subprocess cwd to the case directory. A relative path
    handed to that subprocess is resolved a second time, against the new cwd,
    so the counterparty was asked for a request that was not where it had been
    told to look. Every case came back NOT_CONSTRUCTIBLE, which the cross-check
    correctly refused to publish.

    The existing tests all passed an absolute workspace, so none of them could
    see it. This one invokes the harness the way the hosted job does.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.expectations = json.loads(
            EXPECTATIONS.read_text(encoding="utf-8"))["GLYPHLOCK"]

    def run_harness(self, workspace: str, output: str) -> dict:
        """Invoke exactly as the workflow does, from a cwd of its own."""
        completed = subprocess.run(
            [sys.executable, str(HARNESS),
             "--cases", str(CASES),
             "--runner", str(subject_root() / "glyphlock" / "runner.py"),
             "--workspace", workspace,
             "--output", output,
             "--party-id", "GLYPHLOCK"],
            cwd=self.cwd, capture_output=True, text=True, timeout=300, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads((self.cwd / output / "RESULTS.json").read_text(encoding="utf-8"))

    def test_a_relative_workspace_still_reaches_the_counterparty(self) -> None:
        """The regression itself: relative paths, hosted-style."""
        results = self.run_harness("build/party/work", "build/party/native")
        statuses = {r["execution_status"] for r in results["results"]}
        self.assertNotIn("NOT_CONSTRUCTIBLE", statuses,
                         "a relative workspace made every case unconstructible")
        self.assertEqual(statuses, {"OK", "NOT_IMPLEMENTED"})

    def test_a_relative_workspace_reproduces_every_frozen_expectation(self) -> None:
        """Correct paths are not enough; the native results must be right."""
        results = self.run_harness("build/party/work", "build/party/native")
        by_case = {r["case_id"]: r for r in results["results"]}
        self.assertEqual(set(by_case), set(self.expectations))
        for case_id, expected in sorted(self.expectations.items()):
            with self.subTest(case=case_id):
                self.assertEqual(by_case[case_id]["native_result"], expected)

    def test_relative_and_absolute_workspaces_agree(self) -> None:
        """The two invocation styles are the same exercise."""
        relative = self.run_harness("build/rel/work", "build/rel/native")
        absolute = self.run_harness(str(self.cwd / "abs" / "work"),
                                    str(self.cwd / "abs" / "native"))
        self.assertEqual(
            {r["case_id"]: canonical_sha256(r["native_result"]) for r in relative["results"]},
            {r["case_id"]: canonical_sha256(r["native_result"]) for r in absolute["results"]},
        )

    def test_the_request_lands_inside_the_declared_workspace(self) -> None:
        self.run_harness("build/party/work", "build/party/native")
        landed = sorted(p.relative_to(self.cwd).as_posix()
                        for p in (self.cwd / "build/party/work").rglob("request.wire"))
        self.assertEqual(len(landed), len(self.expectations))
        self.assertTrue(all(p.startswith("build/party/work/X-C-") for p in landed))


class PartyDomainWithoutCounterpartyTest(unittest.TestCase):
    def test_a_missing_counterparty_is_an_availability_fact(self) -> None:
        """TEST 6: missing infrastructure yields no semantic conclusion."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            completed = subprocess.run(
                [sys.executable, str(HARNESS),
                 "--cases", str(CASES),
                 "--runner", str(root / "absent" / "runner.py"),
                 "--workspace", str(root / "work"),
                 "--output", str(root / "native")],
                capture_output=True, text=True, timeout=60, check=False,
            )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("EXECUTION UNAVAILABLE", completed.stdout)


if __name__ == "__main__":
    unittest.main()
