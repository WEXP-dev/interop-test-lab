#!/usr/bin/env python3
"""Read one intake submission as data and prepare the automatic reply.

This is the unprivileged half of the intake acknowledgement. It holds no write
credential. It parses the text of an issue created from the intake form, finds
links to public files on GitHub, fetches those files as bytes, and records
their SHA-256 and size. Nothing it reads is executed, interpolated into a shell
command, or echoed back: the reply is built only from values this module has
validated against a narrow character set.

The submitter's own words never decide the route. The route comes from
``selfservice/routing.py``; the only fact taken from the form is whether the
private-material box is ticked, which can only make handling more careful.

Standard library only. Network access is limited to two fixed hosts and can be
replaced by a fake in tests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from selfservice import routing  # noqa: E402  (path set above; the script runs with -I)

MAX_BODY_BYTES = 64 * 1024
MAX_LINKS = 8
MAX_FILE_BYTES = 2 * 1024 * 1024
TIMEOUT_SECONDS = 15

API_HOST = "api.github.com"
RAW_HOST = "raw.githubusercontent.com"
IETF_HOST = "www.ietf.org"
FIXED_HOSTS = (API_HOST, RAW_HOST, IETF_HOST)
MAX_DRAFTS = 4
MAX_RELATION_REPOSITORIES = 3
MARKER = "<!-- interop-intake-acknowledgement -->"

FORM_MARKER = "### What is your system, specification or project called?"
PRIVATE_HEADING = "### Private material"

NAME = r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9_])?"
SEGMENT = r"[A-Za-z0-9._-]+"
PATH = rf"{SEGMENT}(?:/{SEGMENT})*"
SHA = r"[0-9a-f]{40}"

URL_RE = re.compile(r"https?://[^\s<>()\[\]\"'`]+")
BLOB_RE = re.compile(rf"^https://github\.com/({NAME})/({NAME})/blob/({SEGMENT})/({PATH})$")
RAW_RE = re.compile(rf"^https://raw\.githubusercontent\.com/({NAME})/({NAME})/({SEGMENT})/({PATH})$")
TREE_RE = re.compile(rf"^https://github\.com/({NAME})/({NAME})/(?:tree|commit)/({SEGMENT})(?:/{PATH})?$")
REPO_RE = re.compile(rf"^https://github\.com/({NAME})/({NAME})/?$")

# An Internet-Draft revision is immutable in the IETF archive, so a draft named
# with its two-digit revision can be pinned by its bytes like a file at a commit.
DRAFT = r"draft-[a-z0-9]+(?:-[a-z0-9]+)*"
DRAFT_REV_RE = re.compile(rf"^({DRAFT})-([0-9]{{2}})$")
DRAFT_TOKEN_RE = re.compile(rf"(?<![A-Za-z0-9/._-]){DRAFT}-[0-9]{{2}}(?![A-Za-z0-9_-])")
DRAFT_URL_RES = (
    re.compile(rf"^https://datatracker\.ietf\.org/doc/(?:html/)?({DRAFT})/([0-9]{{2}})/?$"),
    re.compile(rf"^https://datatracker\.ietf\.org/doc/(?:html/)?({DRAFT})/?$"),
    re.compile(rf"^https://www\.ietf\.org/archive/id/({DRAFT})\.(?:txt|xml|html)$"),
)

ROUTE_LABELS = {
    routing.JOINT_RESEARCH: "route:research",
    routing.ASSISTED_REVIEW: "route:assisted",
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # a redirect could leave the fixed hosts
        return None


def _open(url: str, token: str | None):
    host = url.split("/")[2]
    if host not in FIXED_HOSTS:
        raise ValueError("host is not on the fixed list")
    headers = {"User-Agent": "interop-intake-acknowledgement"}
    if token and host == API_HOST:  # the token is never sent to the raw-content host
        headers["Authorization"] = "Bearer " + token
        headers["Accept"] = "application/vnd.github+json"
    opener = urllib.request.build_opener(_NoRedirect)
    return opener.open(urllib.request.Request(url, headers=headers), timeout=TIMEOUT_SECONDS)


def http_fetch(url: str, token: str | None = None) -> bytes | None:
    """Bytes of ``url``, or None when it cannot be read within the limits."""
    try:
        with _open(url, token) as response:
            data = response.read(MAX_FILE_BYTES + 1)
    except (urllib.error.URLError, ValueError, OSError):
        return None
    return data if len(data) <= MAX_FILE_BYTES else None


def is_form_submission(body: str) -> bool:
    return FORM_MARKER in body


def private_box_ticked(body: str) -> bool:
    at = body.find(PRIVATE_HEADING)
    if at == -1:
        return False
    section = body[at + len(PRIVATE_HEADING):].split("\n### ", 1)[0]
    return bool(re.search(r"^\s*-\s*\[[xX]\]", section, re.M))


def clean_path(path: str) -> bool:
    return all(part not in ("", ".", "..") for part in path.split("/"))


def classify(url: str) -> dict | None:
    """A GitHub link reduced to validated parts, or None for anything else."""
    url = url.rstrip(".,;:!?")
    for pattern, kind in ((BLOB_RE, "file"), (RAW_RE, "file")):
        m = pattern.match(url)
        if m and clean_path(m.group(4)):
            return {"kind": kind, "owner": m.group(1), "repo": m.group(2),
                    "ref": m.group(3), "path": m.group(4)}
    m = TREE_RE.match(url)
    if m:
        return {"kind": "revision", "owner": m.group(1), "repo": m.group(2), "ref": m.group(3)}
    m = REPO_RE.match(url)
    if m:
        return {"kind": "repository", "owner": m.group(1), "repo": m.group(2)}
    return None


def classify_draft(text: str) -> dict | None:
    """An Internet-Draft named with or without its revision, or None."""
    text = text.rstrip(".,;:!?")
    m = DRAFT_REV_RE.match(text)
    if m:
        return {"name": m.group(1), "rev": m.group(2)}
    for pattern in DRAFT_URL_RES:
        m = pattern.match(text)
        if not m:
            continue
        if m.lastindex == 2:
            return {"name": m.group(1), "rev": m.group(2)}
        # A trailing two-digit group is read as the revision. If that reading is
        # wrong the archive has no such text, and the reply says so.
        tail = DRAFT_REV_RE.match(m.group(1))
        if tail:
            return {"name": tail.group(1), "rev": tail.group(2)}
        return {"name": m.group(1), "rev": None}
    return None


def relation(login: str | None, repositories: list[tuple[str, str]], fetch, token) -> dict:
    """What GitHub itself shows about the submitting account and the linked repositories.

    Only public facts are used, and only these three. A statement by the
    submitter about who they are is never taken from the form.
    """
    if not login or not re.fullmatch(NAME, login):
        return {"relation": "not-established", "repository": None}
    for owner, repo in repositories[:MAX_RELATION_REPOSITORIES]:
        if owner.lower() == login.lower():
            return {"relation": "repository-owner", "repository": f"{owner}/{repo}"}
    for owner, repo in repositories[:MAX_RELATION_REPOSITORIES]:
        if fetch(f"https://{API_HOST}/orgs/{owner}/public_members/{login}", token) is not None:
            return {"relation": "organization-public-member", "repository": f"{owner}/{repo}"}
    for owner, repo in repositories[:MAX_RELATION_REPOSITORIES]:
        data = fetch(f"https://{API_HOST}/repos/{owner}/{repo}/commits?author={login}&per_page=1", token)
        try:
            listed = json.loads(data) if data else []
        except ValueError:
            listed = []
        if isinstance(listed, list) and listed:
            return {"relation": "repository-contributor", "repository": f"{owner}/{repo}"}
    return {"relation": "not-established", "repository": None}


def resolve_commit(owner: str, repo: str, ref: str, fetch, token) -> str | None:
    if re.fullmatch(SHA, ref):
        return ref
    data = fetch(f"https://{API_HOST}/repos/{owner}/{repo}/commits/{ref}", token)
    try:
        sha = json.loads(data)["sha"] if data else None
    except (ValueError, KeyError, TypeError):
        return None
    return sha if isinstance(sha, str) and re.fullmatch(SHA, sha) else None


def examine(body: str, fetch=http_fetch, token: str | None = None, login: str | None = None) -> dict:
    """Everything the reply needs, as validated values only."""
    body = body.encode("utf-8", "replace")[:MAX_BODY_BYTES].decode("utf-8", "replace")
    urls, seen = [], set()
    for match in URL_RE.finditer(body):
        url = match.group(0)
        if url not in seen:
            seen.add(url)
            urls.append(url)
    files, revisions, repositories, other_hosts, unresolved = [], [], [], 0, 0
    drafts, drafts_without_revision, draft_names, linked = [], 0, [], []
    for token_match in DRAFT_TOKEN_RE.finditer(URL_RE.sub(" ", body)):
        draft_names.append(token_match.group(0))
    for url in urls:
        draft = classify_draft(url)
        if draft is not None:
            draft_names.append(draft["name"] + ("-" + draft["rev"] if draft["rev"] else ""))
            continue
        link = classify(url)
        if link is None:
            other_hosts += 1
            continue
        if (link["owner"], link["repo"]) not in linked:
            linked.append((link["owner"], link["repo"]))
        if len(files) + len(revisions) + len(repositories) + unresolved >= MAX_LINKS:
            break
        owner, repo = link["owner"], link["repo"]
        if link["kind"] == "repository":
            sha = resolve_commit(owner, repo, "HEAD", fetch, token)
            if sha:
                repositories.append({"owner": owner, "repo": repo, "head": sha})
            else:
                unresolved += 1
            continue
        sha = resolve_commit(owner, repo, link["ref"], fetch, token)
        if sha is None:
            unresolved += 1
            continue
        pinned_by_submitter = sha == link["ref"]
        if link["kind"] == "revision":
            revisions.append({"owner": owner, "repo": repo, "commit": sha,
                              "pinned_by_submitter": pinned_by_submitter})
            continue
        data = fetch(f"https://{RAW_HOST}/{owner}/{repo}/{sha}/{link['path']}", None)
        if data is None:
            unresolved += 1
            continue
        files.append({"owner": owner, "repo": repo, "commit": sha, "path": link["path"],
                      "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                      "pinned_by_submitter": pinned_by_submitter})
    seen_drafts = set()
    for name in draft_names:
        draft = classify_draft(name) or {"name": name, "rev": None}
        key = (draft["name"], draft["rev"])
        if key in seen_drafts:
            continue
        seen_drafts.add(key)
        if draft["rev"] is None:
            drafts_without_revision += 1
            continue
        if len(drafts) >= MAX_DRAFTS:
            break
        data = fetch(f"https://{IETF_HOST}/archive/id/{draft['name']}-{draft['rev']}.txt", None)
        if data is None:
            unresolved += 1
            continue
        drafts.append({"name": draft["name"], "rev": draft["rev"],
                       "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    initiator = relation(login, linked, fetch, token)
    private = private_box_ticked(body)
    decision = routing.route({"requires_private_material": private,
                              "existing_mapping_known": False})
    return {"files": files, "revisions": revisions, "repositories": repositories,
            "drafts": drafts, "drafts_without_revision": drafts_without_revision,
            "initiator": initiator,
            "links_to_other_hosts": other_hosts, "links_not_resolved": unresolved,
            "private_material": private, "route": decision["route"],
            "route_label": ROUTE_LABELS[decision["route"]]}


def render(found: dict) -> str:
    """The reply. Built from validated values; the submitter's prose is never quoted."""
    out = [MARKER,
           "Thank you. This reply is automatic: it was produced from the form within minutes, "
           "and nobody has read your submission yet. If you edit your submission, this reply "
           "is brought up to date.", ""]
    if found["private_material"]:
        out += ["**You ticked the private-material box.** Please send nothing private here. "
                "This is a public issue. A maintainer will first confirm whether a suitable "
                "route is available.", ""]
    pinned = bool(found["files"] or found["drafts"])
    if pinned:
        out += ["**Public bytes pinned from your links.** These exact bytes are what any "
                "mapping and any result will refer to. Pinning records which public bytes a "
                "link pointed to; it is not a review and not an endorsement.", ""]
    if found["drafts"]:
        out += ["| Internet-Draft | Revision | SHA-256 of the archived text | Bytes |", "|---|---|---|---|"]
        for d in found["drafts"]:
            out.append(f"| `{d['name']}` | {d['rev']} | `{d['sha256']}` | {d['bytes']} |")
        out.append("")
    if found["files"]:
        out += [
                "| Repository | Commit | Path | SHA-256 | Bytes |", "|---|---|---|---|---|"]
        for f in found["files"]:
            out.append(f"| `{f['owner']}/{f['repo']}` | `{f['commit']}` | `{f['path']}` | "
                       f"`{f['sha256']}` | {f['bytes']} |")
        if any(not f["pinned_by_submitter"] for f in found["files"]):
            out += ["", "Some links named a branch or tag. They were resolved to the commit "
                    "shown, as it stood when this reply was written."]
        out.append("")
    if not pinned:
        out += ["**No public bytes could be pinned yet.** Edit your submission and add either "
                "the name of an Internet-Draft with its revision, such as "
                "`draft-example-record-02`, or a link to a sample record on GitHub: open the "
                "file, press `y`, and copy the address. A branch link also works; it is "
                "resolved to today's commit. This reply then updates itself.", ""]
    if found["drafts_without_revision"]:
        out += [f"{found['drafts_without_revision']} Internet-Draft(s) were named without a "
                "revision. Add the two-digit revision so the exact text can be pinned.", ""]
    for r in found["revisions"]:
        out.append(f"- Revision noted: `{r['owner']}/{r['repo']}` at `{r['commit']}`.")
    for r in found["repositories"]:
        out.append(f"- Repository noted: `{r['owner']}/{r['repo']}`; its default branch is at "
                   f"`{r['head']}` today. No file was named, so no bytes are pinned from it.")
    if found["revisions"] or found["repositories"]:
        out.append("")
    notes = []
    if found["links_to_other_hosts"]:
        notes.append(f"{found['links_to_other_hosts']} link(s) to other hosts were not fetched")
    if found["links_not_resolved"]:
        notes.append(f"{found['links_not_resolved']} GitHub link(s) could not be read "
                     "(missing, private, too large, or not a file)")
    if notes:
        out += ["Not used: " + "; ".join(notes) + ".", ""]
    if found["route"] == routing.JOINT_RESEARCH:
        out += ["**Route: research it with us.** For a format we have not mapped before, the "
                "mapping is the open question, so nothing runs automatically. What happens next:",
                "",
                "1. We write down how your record maps to a normalized input of "
                "[draft-sergeev-wexp-core-02](https://datatracker.ietf.org/doc/draft-sergeev-wexp-core/02/), "
                "together with the results we expect, before any appraiser runs.",
                "2. You read the mapping and tell us where it misreads your format. Your "
                "corrections go in as a separate revision, still before any run.",
                "3. Two appraisers run on the frozen inputs, and you get a scoped written "
                "result. Its wording and the attribution are agreed with you before anything "
                "is published.", ""]
    else:
        out += ["**Route: review it with us.** A maintainer looks at the case before anything "
                "else happens.", ""]
    who = found["initiator"]
    shown = {"repository-owner": "the account that opened this check owns",
             "organization-public-member": "the account that opened this check is a public member of the organization that owns",
             "repository-contributor": "the account that opened this check has commits in"}
    if who["relation"] in shown:
        out += [f"**Who is asking.** GitHub shows that {shown[who['relation']]} "
                f"`{who['repository']}`."]
    else:
        out += ["**Who is asking.** GitHub shows no public link between the account that opened "
                "this check and the linked material. That is fine. If you are an author of the "
                "format, say so; it is confirmed with you directly before any result names you."]
    out += ["A published result states who initiated the check and how that was established. "
            "You can ask not to be named.", ""]
    out += ["A weaker claim, or \"this is outside what Core appraises\", is a valid result. "
            "No response-time commitment is offered; this intake is experimental.", ""]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--comment", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    args = parser.parse_args()
    import os
    event = json.loads(args.event.read_text(encoding="utf-8"))
    issue = event.get("issue") or {}
    body = issue.get("body") or ""
    action = event.get("action")
    author = (issue.get("user") or {}).get("login")
    sender = (event.get("sender") or {}).get("login")
    # An edit is acted on only when the submitter made it and the check is open.
    stale = action not in ("opened", "edited") or issue.get("state") != "open" or (
        action == "edited" and (not author or author != sender))
    if stale or not isinstance(body, str) or not is_form_submission(body):
        args.result.write_text(json.dumps({"action": "skip"}) + "\n", encoding="utf-8")
        args.comment.write_text("", encoding="utf-8")
        print("not an intake form submission; nothing to do")
        return 0
    found = examine(body, token=os.environ.get(args.token_env) or None,
                    login=author if isinstance(author, str) else None)
    args.comment.write_text(render(found), encoding="utf-8")
    args.result.write_text(json.dumps({"action": "reply", "event_action": action, **found},
                                      indent=1, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({k: found[k] for k in ("route_label", "links_to_other_hosts",
                                            "links_not_resolved", "private_material")}))
    print("files pinned:", len(found["files"]), "drafts pinned:", len(found["drafts"]),
          "relation:", found["initiator"]["relation"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
