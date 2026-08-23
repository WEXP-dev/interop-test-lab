"""The deny scan: secrets, personal paths, protected values, review triggers."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from support import minimal_allowlist, new_sentinel

import disclosure_scan

PUBLIC_PIN = "8753d05f139d1cf0f0f63fa7a58a1886a27098b1"


class DisclosureScanTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.staging = Path(self._tmp.name) / "evidence"
        self.staging.mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)
        # A synthetic identity, invented here. The real trigger set is held as
        # digests precisely so that a test does not have to write one out.
        self.trigger_term = "Zarquonix"
        salt = "test-salt"
        self.triggers = (salt, frozenset({
            hashlib.sha256((salt + self.trigger_term.lower()).encode()).hexdigest()}))

    def stage(self, name: str, text: str) -> None:
        path = self.staging / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def scan(self, *, protected: list[str] | None = None,
             allowlist: dict | None = None, pins: list[str] | None = None,
             triggers: tuple[str, frozenset[str]] | None = None) -> dict:
        return disclosure_scan.scan(
            self.staging,
            allowlist=allowlist or minimal_allowlist([]),
            protected_values=protected or [],
            public_pins=pins if pins is not None else [PUBLIC_PIN],
            strategic_triggers=triggers if triggers is not None else self.triggers,
        )

    def families(self, report: dict) -> set[str]:
        return {finding["family"] for finding in report["findings"]}

    def test_a_clean_bundle_passes(self) -> None:
        self.stage("outcome.json", json.dumps({"reported_outcome": "MAPPING_REQUIRED"}))
        self.stage("native/glyphlock/PARTY-DOMAIN.json",
                   json.dumps({"source_commit": PUBLIC_PIN}))
        report = self.scan()
        self.assertEqual(report["status"], "CLEAN", report["findings"])

    def test_a_private_key_block_fails_closed(self) -> None:
        self.stage("outcome.json", "-----BEGIN OPENSSH PRIVATE KEY-----\n")
        report = self.scan()
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("secret", self.families(report))

    def test_a_credential_shape_fails_closed(self) -> None:
        for text in ("ghp_" + "a" * 30, "github_pat_" + "b" * 30,
                     "Authorization: Bearer " + "c" * 20,
                     "sk-" + "d" * 30, "AKIA" + "E" * 16, "password: hunter2"):
            with self.subTest(text=text[:12]):
                self.stage("outcome.json", text + "\n")
                self.assertIn("secret", self.families(self.scan()))

    def test_a_personal_or_local_path_fails_closed(self) -> None:
        """§17 B: a developer's filesystem is not part of a publication bundle."""
        for text in ("/Users/example/.codex/sessions/0000/00/00/",
                     "/home/developer/wexp/",
                     r"C:\Users\dev\wexp",
                     "/Volumes/Macintosh HD/work",
                     "Library/CloudStorage/GoogleDrive-x",
                     "OneDrive/wexp", "Dropbox/wexp",
                     "~/.ssh/id_ed25519", "keys in .gnupg/private-keys-v1.d"):
            with self.subTest(text=text):
                self.stage("outcome.json", text + "\n")
                self.assertIn("personal-or-local-path", self.families(self.scan()))

    def test_the_runner_workspace_path_is_not_a_personal_path(self) -> None:
        """A hosted runner's own working directory is infrastructure, not a person."""
        self.stage("outcome.json", "built under /home/runner/work/lab/lab\n")
        self.assertEqual(self.scan()["status"], "CLEAN")

    def test_a_protected_runtime_value_fails_closed(self) -> None:
        """TEST 5: the private tooling pin cannot reach an uploaded artifact."""
        sentinel = new_sentinel()
        self.stage("outcome.json", f'{{"note":"{sentinel}"}}\n')
        report = self.scan(protected=[sentinel])
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("protected-value", self.families(report))
        # The report names the rule and the path, never the value itself.
        self.assertNotIn(sentinel, json.dumps(report))

    def test_an_undeclared_commit_identity_fails_closed(self) -> None:
        """A 40-hex object id that is not a declared public pin is refused."""
        self.stage("outcome.json", '{"pin":"' + "f" * 40 + '"}\n')
        report = self.scan()
        self.assertIn("unattributed-commit-identity", self.families(report))

    def test_a_declared_public_pin_is_accepted(self) -> None:
        self.stage("outcome.json", '{"pin":"' + PUBLIC_PIN + '"}\n')
        self.assertEqual(self.scan()["status"], "CLEAN")

    def test_a_written_down_object_id_is_accepted(self) -> None:
        """A public placeholder is admitted by writing it down, not by weakening the rule."""
        placeholder = "a" * 40
        self.stage("frozen-cases.json", '{"git_commit":"' + placeholder + '"}\n')
        self.assertEqual(self.scan()["status"], "FAIL")

        allowlist = minimal_allowlist([])
        allowlist["declared_object_ids"] = [
            {"id": placeholder, "where": "the shared-subject fixture",
             "why": "synthetic placeholder; names no repository"}]
        self.assertEqual(self.scan(allowlist=allowlist)["status"], "CLEAN")

    def test_the_repository_allowlist_declares_its_placeholder(self) -> None:
        allowlist = json.loads(
            (Path(disclosure_scan.__file__).resolve().parents[1]
             / "publication" / "ALLOWLIST.json").read_text(encoding="utf-8"))
        declared = {item["id"] for item in allowlist["declared_object_ids"]}
        self.assertIn("a" * 40, declared)
        for item in allowlist["declared_object_ids"]:
            with self.subTest(object_id=item["id"]):
                self.assertTrue(item["why"], "every declared object id carries a reason")

    def test_a_non_public_organisation_repository_fails_closed(self) -> None:
        """The rule names the public repositories, never the private inventory."""
        self.stage("outcome.json", '{"tooling":"WEXP-dev/some-private-repo"}\n')
        self.assertIn("private-identity", self.families(self.scan()))

    def test_a_public_organisation_repository_is_accepted(self) -> None:
        self.stage("outcome.json", '{"party":"WEXP-dev/interop-test-subject"}\n')
        self.assertEqual(self.scan()["status"], "CLEAN")

    def test_a_commercial_word_is_a_review_trigger_that_fails_until_written_down(self) -> None:
        """§17 H: the word does not prove leakage; it forces an explicit decision."""
        self.stage("outcome.json", '{"note":"per-customer pricing was not compared"}\n')
        report = self.scan()
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("strategic-review-trigger", self.families(report))

        allowed = minimal_allowlist([], exceptions=[
            {"path": "outcome.json", "keyword": "customer", "why": "reviewed"},
            {"path": "outcome.json", "keyword": "pricing", "why": "reviewed"}])
        self.assertEqual(self.scan(allowlist=allowed)["status"], "CLEAN")

    def test_an_identity_trigger_matches_by_digest_and_is_never_echoed(self) -> None:
        """The identity set is held as digests, so nothing names it — here included."""
        self.stage("outcome.json", '{"note":"produced by ' + self.trigger_term + '"}\n')
        report = self.scan()
        self.assertEqual(report["status"], "FAIL")
        rules = {f["rule"] for f in report["findings"]}
        self.assertTrue(any(r.startswith("identity:") for r in rules))
        # The report names a digest prefix, never the term it matched.
        self.assertNotIn(self.trigger_term, json.dumps(report))

    def test_an_identity_trigger_matches_case_insensitively(self) -> None:
        self.stage("outcome.json", '{"note":"' + self.trigger_term.upper() + '"}\n')
        self.assertIn("strategic-review-trigger", self.families(self.scan()))

    def test_an_identity_trigger_can_be_admitted_by_its_digest(self) -> None:
        self.stage("outcome.json", '{"note":"' + self.trigger_term + '"}\n')
        digest = next(iter(self.triggers[1]))
        allowed = minimal_allowlist([], exceptions=[
            {"path": "outcome.json", "keyword": f"identity:{digest[:12]}",
             "why": "reviewed: the identity is already public in this context"}])
        self.assertEqual(self.scan(allowlist=allowed)["status"], "CLEAN")

    def test_the_repository_trigger_file_publishes_no_terms(self) -> None:
        document = json.loads(
            (Path(disclosure_scan.__file__).resolve().parents[1]
             / "publication" / "STRATEGIC-TRIGGERS.json").read_text(encoding="utf-8"))
        self.assertEqual(document["algorithm"], "sha256")
        self.assertTrue(document["digests"])
        for digest in document["digests"]:
            with self.subTest(digest=digest[:12]):
                self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertTrue(any("not secrecy" in n for n in document["non_claims"]))

    def test_a_non_utf8_artifact_fails_closed(self) -> None:
        (self.staging / "outcome.json").write_bytes(b"\xff\xfe\x00binary")
        report = self.scan()
        self.assertIn("undecodable", self.families(report))


if __name__ == "__main__":
    unittest.main()
