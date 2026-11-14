#!/usr/bin/env python3
"""Build the address of the interoperability-check form with some answers already filled in.

For an invitation: the person opens the address, reads the form, ticks the confirmation and
submits. Nothing is submitted for them. Only public facts go in: a name, a public source, a
revision, a link to public example material. Standard library only.

    python3 tools/prefill_link.py --name "Example Receipts" --example https://github.com/acme/r/blob/main/r.json
"""

from __future__ import annotations

import argparse
import sys
import urllib.parse

FORM = "https://github.com/WEXP-dev/interop-test-lab/issues/new"
TEMPLATE = "interop-check.yml"
FIELDS = ("name", "source", "revision", "example")
MAX_FIELD = 300
MAX_ADDRESS = 2000


def build(**answers: str | None) -> str:
    query = [("template", TEMPLATE)]
    name = (answers.get("name") or "").strip()
    if not name:
        raise ValueError("a name is required")
    query.append(("title", f"Interop check: {name}"))
    for field in FIELDS:
        value = (answers.get(field) or "").strip()
        if not value:
            continue
        if len(value) > MAX_FIELD or any(ord(c) < 32 for c in value):
            raise ValueError(f"{field} must be one plain line of at most {MAX_FIELD} characters")
        query.append((field, value))
    address = FORM + "?" + urllib.parse.urlencode(query, quote_via=urllib.parse.quote)
    if len(address) > MAX_ADDRESS:
        raise ValueError("the address would be too long; shorten the answers")
    return address


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for field in FIELDS:
        parser.add_argument(f"--{field}", required=field == "name")
    args = parser.parse_args(argv)
    try:
        print(build(**vars(args)))
    except ValueError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
