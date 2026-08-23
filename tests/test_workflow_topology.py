"""The trust boundary, asserted as a property of the workflow file.

A comment saying "this job holds no credential" is worth nothing the day
somebody adds a step. These tests read the workflow and check the shape:
which job holds the secret, which job runs somebody else's code, and what may
happen after the disclosure gate.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from support import REPO_ROOT

from workflow_reader import (
    action_references, is_sha_pinned, parse_jobs, triggers, workflow_paths,
)

HOSTED = REPO_ROOT / ".github" / "workflows" / "interop-hosted.yml"

COUNTERPARTY_REPOSITORY = "WEXP-dev/interop-test-subject"
PRIVATE_REPOSITORY = "WEXP-dev/wexp-work"
COUNTERPARTY_CHECKOUT_PATH = "subject/"

#: Steps that make up the publication gate, in the order they must occur.
#: Matched on the invocation, not the bare path: the staged reproduction notes
#: name these tools in prose, and prose is not a step that runs them.
GATE_SEQUENCE = ("python3 tools/publication_gate.py", "python3 tools/disclosure_scan.py",
                 "python3 tools/post_gate_check.py")


class HostedTopologyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = HOSTED.read_text(encoding="utf-8")
        self.jobs = parse_jobs(self.text)

    # -- domain separation --------------------------------------------------

    def test_the_two_domains_exist(self) -> None:
        self.assertEqual(set(self.jobs), {"counterparty", "coordinate"})

    def test_the_counterparty_domain_holds_no_secret(self) -> None:
        """§17 F: untrusted executable code never shares a job with a credential."""
        self.assertNotIn("secrets.", self.jobs["counterparty"].text)

    def test_the_counterparty_domain_holds_no_private_checkout(self) -> None:
        self.assertNotIn(PRIVATE_REPOSITORY, self.jobs["counterparty"].text)

    def test_the_coordination_domain_never_checks_out_the_counterparty(self) -> None:
        """The defect this work removed: co-located private and external code."""
        self.assertNotIn(COUNTERPARTY_REPOSITORY, self.jobs["coordinate"].text)

    def test_the_coordination_domain_never_executes_counterparty_code(self) -> None:
        offenders = [step.name for step in self.jobs["coordinate"].steps
                     if COUNTERPARTY_CHECKOUT_PATH in step.text]
        self.assertEqual(offenders, [])

    def test_no_job_holds_both_a_secret_and_the_counterparty(self) -> None:
        for name, job in self.jobs.items():
            with self.subTest(job=name):
                self.assertFalse(
                    "secrets." in job.text and COUNTERPARTY_REPOSITORY in job.text,
                    f"job {name} co-locates a credential with externally controlled code",
                )

    def test_the_boundary_is_crossed_by_artifact_only(self) -> None:
        self.assertIn("upload-artifact", self.jobs["counterparty"].text)
        self.assertIn("download-artifact", self.jobs["coordinate"].text)
        self.assertIn("needs: counterparty", self.jobs["coordinate"].text)

    # -- gate ordering ------------------------------------------------------

    def test_the_gate_runs_in_order(self) -> None:
        job = self.jobs["coordinate"]
        indices = [job.step_index(marker) for marker in GATE_SEQUENCE]
        self.assertEqual(indices, sorted(indices),
                         "allowlist, deny scan and immutability check are out of order")

    def test_execution_and_staging_precede_the_gate(self) -> None:
        job = self.jobs["coordinate"]
        gate = job.step_index("python3 tools/publication_gate.py")
        for marker in ("run.py \\", "python3 tools/ingest_native.py",
                       "cat > build/evidence/REPRODUCTION.md"):
            with self.subTest(marker=marker):
                self.assertLess(job.step_index(marker), gate)

    def test_nothing_mutating_follows_the_gate(self) -> None:
        """§5: after the final gate, only deterministic upload mechanics."""
        job = self.jobs["coordinate"]
        last_gate = job.step_index("python3 tools/post_gate_check.py")
        for step in job.steps[last_gate + 1:]:
            with self.subTest(step=step.name):
                self.assertNotIn("run:", step.text,
                                 "a shell step runs after the immutability check")
                self.assertIn("upload-artifact", step.text)

    def test_the_upload_is_last(self) -> None:
        job = self.jobs["coordinate"]
        self.assertEqual(job.step_index("upload-artifact"), len(job.steps) - 1)

    def test_the_upload_does_not_run_unconditionally(self) -> None:
        """A refused gate must not publish the tree it refused."""
        job = self.jobs["coordinate"]
        upload = job.steps[job.step_index("upload-artifact")]
        self.assertNotIn("always()", upload.text)
        self.assertNotIn("if:", upload.text)

    def test_the_upload_publishes_only_the_gated_tree(self) -> None:
        job = self.jobs["coordinate"]
        upload = job.steps[job.step_index("upload-artifact")]
        self.assertIn("path: build/evidence/", upload.text)

    # -- ordinary workflow hygiene -----------------------------------------

    def test_no_pull_request_trigger_anywhere(self) -> None:
        for path in workflow_paths(REPO_ROOT):
            with self.subTest(workflow=path.name):
                names = triggers(path.read_text(encoding="utf-8"))
                self.assertNotIn("pull_request_target", names)
                if path == HOSTED:
                    self.assertNotIn("pull_request", names)

    def test_every_action_is_sha_pinned(self) -> None:
        for path in workflow_paths(REPO_ROOT):
            for reference in action_references(path.read_text(encoding="utf-8")):
                with self.subTest(workflow=path.name, action=reference):
                    self.assertTrue(is_sha_pinned(reference),
                                    f"{reference} is not pinned to a commit id")

    def test_every_workflow_declares_least_privilege(self) -> None:
        for path in workflow_paths(REPO_ROOT):
            text = path.read_text(encoding="utf-8")
            with self.subTest(workflow=path.name):
                self.assertIn("permissions:\n  contents: read", text)

    def test_every_checkout_refuses_to_persist_credentials(self) -> None:
        for path in workflow_paths(REPO_ROOT):
            text = path.read_text(encoding="utf-8")
            checkouts = text.count("uses: actions/checkout@")
            with self.subTest(workflow=path.name):
                self.assertEqual(text.count("persist-credentials: false"), checkouts)

    def test_secrets_are_only_referenced_in_the_coordination_domain(self) -> None:
        for name, job in self.jobs.items():
            if name == "coordinate":
                continue
            with self.subTest(job=name):
                self.assertNotIn("secrets.", job.text)


if __name__ == "__main__":
    unittest.main()
