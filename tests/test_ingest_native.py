"""A party-domain artifact is untrusted input, and is treated as such."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import write_json

from staging import GateFailure, canonical_sha256
import ingest_native

SEALED = {"format": "GLYPHLOCK-RESULT/1", "seal-state": "GLYPH_SEALED",
          "ward-reached": "3", "notes": "ward reached its declared depth"}
BROKEN = {"format": "GLYPHLOCK-RESULT/1", "seal-state": "GLYPH_BROKEN",
          "ward-reached": "0", "notes": "no attestation accompanies the ward"}


def results_payload(results: list[dict]) -> dict:
    return {"record_kind": "interop-lab-native-results", "party_id": "GLYPHLOCK",
            "case_count": len(results), "results": results}


def domain_payload(commit: str = "a" * 40) -> dict:
    return {"record_kind": "interop-lab-party-domain", "party_id": "GLYPHLOCK",
            "source_repository": "WEXP-dev/interop-test-subject",
            "source_commit": commit, "runner_sha256": "b" * 64,
            "isolation": {"private_wexp_source_present": False,
                          "credential_material_present": False,
                          "publication_staging_present": False}}


def bundle(identities: dict[str, str]) -> dict:
    return {"native_result_identities": {"GLYPHLOCK": identities}}


class IngestTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.native = Path(self._tmp.name) / "counterparty-native"
        self.native.mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)

    def stage(self, results: dict, domain: dict | None = None) -> None:
        write_json(self.native / "RESULTS.json", results)
        write_json(self.native / "PARTY-DOMAIN.json", domain or domain_payload())

    def test_an_agreeing_artifact_is_accepted(self) -> None:
        self.stage(results_payload([
            {"case_id": "X-C-001", "execution_status": "OK", "native_result": SEALED}]))
        results, _ = ingest_native.load_incoming(self.native)
        report = ingest_native.cross_check(
            results, bundle({"X-C-001": canonical_sha256(SEALED)}), party_id="GLYPHLOCK")
        self.assertEqual(report["status"], "AGREES")

    def test_a_divergent_counterparty_result_is_refused(self) -> None:
        """The run may not describe a counterparty run that did not happen."""
        self.stage(results_payload([
            {"case_id": "X-C-001", "execution_status": "OK", "native_result": BROKEN}]))
        results, _ = ingest_native.load_incoming(self.native)
        with self.assertRaises(GateFailure) as raised:
            ingest_native.cross_check(
                results, bundle({"X-C-001": canonical_sha256(SEALED)}), party_id="GLYPHLOCK")
        self.assertIn("X-C-001", str(raised.exception))
        self.assertIn("No semantic conclusion", str(raised.exception))

    def test_a_case_set_disagreement_is_refused(self) -> None:
        self.stage(results_payload([
            {"case_id": "X-C-001", "execution_status": "OK", "native_result": SEALED},
            {"case_id": "X-C-999", "execution_status": "OK", "native_result": SEALED}]))
        results, _ = ingest_native.load_incoming(self.native)
        with self.assertRaises(GateFailure) as raised:
            ingest_native.cross_check(
                results, bundle({"X-C-001": canonical_sha256(SEALED)}), party_id="GLYPHLOCK")
        self.assertIn("X-C-999", str(raised.exception))

    def test_a_null_native_result_is_carried_faithfully(self) -> None:
        """A case the counterparty cannot execute has an identity of its own."""
        self.stage(results_payload([
            {"case_id": "X-C-007", "execution_status": "NOT_IMPLEMENTED",
             "native_result": None}]))
        results, _ = ingest_native.load_incoming(self.native)
        report = ingest_native.cross_check(
            results, bundle({"X-C-007": canonical_sha256(None)}), party_id="GLYPHLOCK")
        self.assertEqual(report["status"], "AGREES")

    def test_an_undeclared_file_in_the_artifact_is_refused(self) -> None:
        self.stage(results_payload([]))
        write_json(self.native / "SMUGGLED.json", {"note": "extra"})
        with self.assertRaises(GateFailure) as raised:
            ingest_native.load_incoming(self.native)
        self.assertIn("SMUGGLED.json", str(raised.exception))

    def test_an_incomplete_artifact_is_refused(self) -> None:
        write_json(self.native / "RESULTS.json", results_payload([]))
        with self.assertRaises(GateFailure) as raised:
            ingest_native.load_incoming(self.native)
        self.assertIn("incomplete", str(raised.exception))

    def test_a_wrong_record_kind_is_refused(self) -> None:
        self.stage({"record_kind": "something-else", "results": []})
        with self.assertRaises(GateFailure):
            ingest_native.load_incoming(self.native)

    def test_a_symlinked_artifact_is_refused(self) -> None:
        self.stage(results_payload([]))
        (self.native / "extra").symlink_to(self.native / "RESULTS.json")
        with self.assertRaises(GateFailure) as raised:
            ingest_native.load_incoming(self.native)
        self.assertIn("symlink", str(raised.exception))

    def test_a_run_with_no_recorded_identities_is_refused(self) -> None:
        self.stage(results_payload([]))
        results, _ = ingest_native.load_incoming(self.native)
        with self.assertRaises(GateFailure):
            ingest_native.cross_check(results, {}, party_id="GLYPHLOCK")


if __name__ == "__main__":
    unittest.main()
