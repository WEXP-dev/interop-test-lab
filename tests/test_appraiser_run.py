"""Running somebody else's appraiser: what it is given, what is read back, and who holds what."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from support import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "tools"))
import appraiser_run  # noqa: E402

from workflow_reader import PINNED_USES_RE, USES_RE, parse_jobs, triggers  # noqa: E402

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "appraiser-corpus-run.yml"
EXPECTED = {"verdict": "downgrade", "substantive_reasons": ["B", "A"], "supported_claims": []}
SENTINEL = "EXPECTATION_SENTINEL_NOT_FOR_THE_IMPLEMENTATION"
ENGINE = ("import json,sys\n"
          "i=sys.argv.index('--input'); json.load(open(sys.argv[i+1]))\n"
          "print(json.dumps(%s))\n")


class Bench:
    """A one-set corpus under a pinned digest, an implementation, and the three steps."""

    def __init__(self, tmp: Path, engine: str):
        self.tmp = tmp
        corpus = {"id": "SET-A", "profiles": {"p": {}}, "cases": [
            {"id": "C1", "input": {"n": 1}, "expected": {**EXPECTED, "note": SENTINEL}},
            {"id": "C2", "input": {"n": 2}, "expected": EXPECTED, "profiles": {"q": {}}}]}
        self.corpus = tmp / "corpus.json"
        self.corpus.write_text(json.dumps(corpus), encoding="utf-8")
        self.pins = {"SET-A": hashlib.sha256(self.corpus.read_bytes()).hexdigest()}
        (tmp / "impl").mkdir()
        (tmp / "impl" / "engine.py").write_text(engine, encoding="utf-8")

    def go(self):
        with mock.patch.dict(appraiser_run.CORPORA, self.pins, clear=True):
            appraiser_run.write_inputs([self.corpus], self.tmp / "in")
            self.record = appraiser_run.run_cases(self.tmp / "in", self.tmp / "out",
                                                  f"{sys.executable} -I -B engine.py", self.tmp / "impl")
            return appraiser_run.compare([self.corpus], self.tmp / "out")


class StepsTest(unittest.TestCase):

    def bench(self, engine):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Bench(Path(tmp.name), engine)

    def test_an_implementation_that_returns_the_expected_result_is_reported_equal(self):
        bench = self.bench(ENGINE % {**EXPECTED, "substantive_reasons": ["A", "B"]})
        report = bench.go()["sets"]["SET-A"]
        self.assertEqual((report["cases"], report["equal_to_expected"]), (2, 1))
        self.assertEqual(report["rows"][0]["missing_components"], ["note"])
        self.assertEqual(report["rows"][0]["differing_components"], [])
        self.assertTrue(report["rows"][1]["equal"])

    def test_the_implementation_is_given_inputs_and_profiles_and_no_expectation(self):
        bench = self.bench(ENGINE % EXPECTED)
        bench.go()
        handed = sorted(p.relative_to(bench.tmp / "in").as_posix() for p in (bench.tmp / "in").rglob("*") if p.is_file())
        self.assertEqual(handed, ["SET-A/C1.input.json", "SET-A/C1.profiles.json", "SET-A/C2.input.json",
                                  "SET-A/C2.profiles.json", "cases.json"])
        for path in (bench.tmp / "in").rglob("*.json"):
            self.assertNotIn(SENTINEL, path.read_text())
            self.assertNotIn("expected", path.read_text())
        self.assertEqual(json.loads((bench.tmp / "in" / "SET-A" / "C2.profiles.json").read_text()), {"q": {}})

    def test_a_corpus_whose_bytes_differ_from_the_pin_is_refused(self):
        bench = self.bench(ENGINE % EXPECTED)
        bench.corpus.write_text(bench.corpus.read_text() + " ", encoding="utf-8")
        with mock.patch.dict(appraiser_run.CORPORA, bench.pins, clear=True), self.assertRaises(appraiser_run.Refusal):
            appraiser_run.write_inputs([bench.corpus], bench.tmp / "in")

    def test_output_that_is_missing_or_not_an_object_is_a_named_problem_not_a_crash(self):
        for engine, problem in (("raise SystemExit(3)\n", "process: exit 3"),
                                ("print('not json')\n", "output is not JSON"),
                                ("print('[1, 2]')\n", "output is not a JSON object"),
                                ("print('[' * 100000)\n", "output is not JSON"),
                                ("import sys\nsys.stdout.write('x' * (2 * 1024 * 1024))\n", "process: output too large")):
            with self.subTest(problem=problem):
                rows = self.bench(engine).go()["sets"]["SET-A"]["rows"]
                self.assertEqual([r.get("problem") for r in rows], [problem, problem])
                self.assertFalse(any(r["equal"] for r in rows))

    def test_an_absent_component_is_not_the_same_as_a_null_one(self):
        expected = {**EXPECTED, "supported_claims": None}
        bench = self.bench(ENGINE % {"verdict": "downgrade", "substantive_reasons": ["A", "B"]})
        bench.corpus.write_text(json.dumps({"id": "SET-A", "profiles": {}, "cases": [
            {"id": "C1", "input": {}, "expected": expected}]}), encoding="utf-8")
        bench.pins = {"SET-A": hashlib.sha256(bench.corpus.read_bytes()).hexdigest()}
        row = bench.go()["sets"]["SET-A"]["rows"][0]
        self.assertFalse(row["equal"])
        self.assertEqual(row["missing_components"], ["supported_claims"])
        self.assertIn("`supported_claims` (absent)", appraiser_run.summary(
            {"vectors_commit": "b" * 40, "sets": {"SET-A": {"cases": 1, "equal_to_expected": 0, "rows": [row]}}},
            "acme/appraiser", "a" * 40))

    def test_a_repeated_key_or_a_non_json_number_is_not_read_as_a_result(self):
        doubled = 'print(\'{"verdict": "reject", "verdict": "downgrade", "substantive_reasons": ["A", "B"], "supported_claims": []}\')\n'
        rows = self.bench(doubled).go()["sets"]["SET-A"]["rows"]
        self.assertEqual(rows[1].get("problem"), "output repeats a key")
        rows = self.bench('print(\'{"verdict": NaN}\')\n').go()["sets"]["SET-A"]["rows"]
        self.assertEqual(rows[1].get("problem"), "output is not JSON")

    def test_the_expected_result_from_a_process_that_did_not_end_normally_is_not_equal(self):
        bench = self.bench(ENGINE % EXPECTED + "raise SystemExit(4)\n")
        rows = bench.go()["sets"]["SET-A"]["rows"]
        self.assertEqual(rows[1], {"id": "C2", "expected_verdict": "downgrade", "process": "exit 4",
                                   "equal": False, "problem": "process: exit 4"})

    def test_without_the_record_of_the_run_nothing_is_equal(self):
        bench = self.bench(ENGINE % EXPECTED)
        bench.go()
        (bench.tmp / "out" / "run.json").write_text('{"SET-A/C2": "exit 0; all good"}', encoding="utf-8")
        with mock.patch.dict(appraiser_run.CORPORA, bench.pins, clear=True):
            rows = appraiser_run.compare([bench.corpus], bench.tmp / "out")["sets"]["SET-A"]["rows"]
        self.assertEqual([r["problem"] for r in rows], ["process: not recorded"] * 2)

    def test_output_without_end_is_stopped_at_the_limit(self):
        bench = self.bench("import sys\nwhile True:\n    sys.stdout.write('x' * 65536)\n")
        with mock.patch.object(appraiser_run, "CASE_TIMEOUT_SECONDS", 20):
            state, printed = appraiser_run.run_one([sys.executable, "-I", "-B", "engine.py"], bench.tmp / "impl")
        self.assertEqual(state, "output too large")
        self.assertEqual(len(printed), appraiser_run.MAX_OUTPUT_BYTES + 1)

    def test_an_extra_component_is_not_equal(self):
        rows = self.bench(ENGINE % {**EXPECTED, "extra": 1}).go()["sets"]["SET-A"]["rows"]
        self.assertFalse(rows[1]["equal"])
        self.assertEqual(rows[1]["components_not_in_the_expectation"], 1)

    def test_a_planted_link_in_the_outputs_is_not_followed(self):
        bench = self.bench(ENGINE % EXPECTED)
        bench.go()
        secret = bench.tmp / "secret.json"
        secret.write_text(json.dumps(EXPECTED), encoding="utf-8")
        target = bench.tmp / "out" / "SET-A" / "C2.json"
        target.unlink()
        os.symlink(secret, target)
        with mock.patch.dict(appraiser_run.CORPORA, bench.pins, clear=True):
            rows = appraiser_run.compare([bench.corpus], bench.tmp / "out")["sets"]["SET-A"]["rows"]
        self.assertEqual(rows[1].get("problem"), "no output")

    def test_nothing_the_implementation_printed_reaches_the_summary(self):
        hostile = {"verdict": "<script>@everyone ${{ secrets.X }}", "substantive_reasons": ["`rm -rf`"],
                   "supported_claims": [], "| injected | column |": 1}
        bench = self.bench(ENGINE % hostile)
        text = appraiser_run.summary(bench.go(), "acme/appraiser", "a" * 40)
        for fragment in ("script", "@everyone", "secrets", "rm -rf", "injected"):
            self.assertNotIn(fragment, text)
        self.assertIn("| `SET-A` / `C2` | downgrade | other |", text)

    def test_the_summary_makes_no_statement_about_meeting_the_specification(self):
        bench = self.bench(ENGINE % EXPECTED)
        text = appraiser_run.summary(bench.go(), "acme/appraiser", "a" * 40).lower()
        for word in ("conform", "certif", "compatible", "compliant", "independent", "passed", "failed"):
            self.assertNotIn(word, text)
        self.assertIn("declaration by its author", text)

    def test_the_implementation_is_named_only_by_a_checked_repository_and_commit(self):
        report = {"vectors_commit": "b" * 40, "sets": {}}
        for repository, commit in (("acme/x`; rm", "a" * 40), ("acme", "a" * 40), ("acme/x", "main"),
                                   ("acme/x/y", "a" * 40)):
            with self.subTest(repository=repository, commit=commit), self.assertRaises(appraiser_run.Refusal):
                appraiser_run.summary(report, repository, commit)


class WorkflowShapeTest(unittest.TestCase):

    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.jobs = parse_jobs(self.text)

    def test_only_a_maintainer_starts_it(self):
        self.assertEqual(set(triggers(self.text)), {"workflow_dispatch"})

    def test_there_are_three_jobs_in_order(self):
        self.assertEqual(list(self.jobs), ["inputs", "run", "compare"])
        self.assertIn("needs: inputs", self.jobs["run"].text)
        self.assertIn("needs: run", self.jobs["compare"].text)

    def test_no_job_can_write_and_no_secret_is_named(self):
        self.assertNotRegex(self.text, r":\s*write\b")
        self.assertEqual(self.text.count("permissions:"), 1)
        self.assertIn("permissions:\n  contents: read\n", self.text)
        self.assertNotIn("secrets.", self.text)
        self.assertNotIn("github.token", self.text)
        self.assertEqual(self.text.count("persist-credentials: false"), self.text.count("actions/checkout@"))

    def test_the_external_code_exists_in_the_run_job_only(self):
        for name in ("inputs", "compare"):
            with self.subTest(job=name):
                self.assertNotIn("implementation", self.jobs[name].text.replace("IMPLEMENTATION", "")
                                 .replace("external implementation", ""))
                self.assertNotIn("inputs.entry", self.jobs[name].text)
                self.assertNotIn("inputs.setup", self.jobs[name].text)
        self.assertIn("git clone --quiet \"https://github.com/${IMPLEMENTATION}.git\" implementation",
                      self.jobs["run"].text)

    def test_the_run_job_never_sees_the_expectations(self):
        run = self.jobs["run"].text
        self.assertNotIn("wexp-vectors", run)
        self.assertNotIn("corpus.json", run)

    def test_typed_values_reach_commands_only_through_the_environment(self):
        for line in self.text.splitlines():
            if "${{ inputs." in line:
                self.assertRegex(line, r"^\s+[A-Z_]+: \$\{\{ inputs\.[a-z]+ \}\}$")

    def test_every_action_is_pinned_to_a_commit(self):
        for line in self.text.splitlines():
            found = USES_RE.match(line)
            if found:
                self.assertRegex(found.group("value"), PINNED_USES_RE)


if __name__ == "__main__":
    unittest.main()
