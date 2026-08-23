"""Shared helpers for the publication staging tree.

Nothing here decides anything about either party. These are byte-level
mechanics: walk a directory, hash a file, read a manifest.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

MANIFEST_NAME = "PUBLICATION-MANIFEST.json"
MANIFEST_RECORD_KIND = "interop-lab-publication-manifest"


class GateFailure(RuntimeError):
    """A publication gate failed closed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value) -> bytes:
    """The framework's deterministic JSON encoding.

    Sorted keys, no insignificant whitespace, UTF-8, trailing newline. This is
    the encoding the interop framework records digests over, and it is stated
    here so a party domain can compute the same identity without holding any
    framework code.
    """
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8") + b"\n"


def canonical_sha256(value) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def walk_staging(root: Path) -> list[str]:
    """Every regular file under ``root``, as sorted POSIX-relative paths.

    A symlink, device node or any other special entry is a hard failure: the
    allowlist speaks about file contents, and a symlink's content is somebody
    else's file.
    """
    root = root.resolve()
    if not root.is_dir():
        raise GateFailure(f"staging root is not a directory: {root}")
    found: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise GateFailure(f"symlink in staging tree: {path.relative_to(root)}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise GateFailure(f"special filesystem entry in staging tree: {path.relative_to(root)}")
        found.append(path.relative_to(root).as_posix())
    return sorted(found)


def build_manifest(root: Path, *, experiment_id: str) -> dict:
    root = root.resolve()
    entries = []
    for relative in walk_staging(root):
        if relative == MANIFEST_NAME:
            continue
        path = root / relative
        entries.append({
            "path": relative,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        })
    return {
        "record_kind": MANIFEST_RECORD_KIND,
        "experiment_id": experiment_id,
        "entry_count": len(entries),
        "entries": entries,
        "non_claims": [
            "This manifest records the exact bytes admitted to publication.",
            "It establishes nothing about either party's protocol.",
        ],
    }


def load_manifest(path: Path) -> dict:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateFailure(f"cannot read publication manifest: {exc}") from exc
    if manifest.get("record_kind") != MANIFEST_RECORD_KIND:
        raise GateFailure("publication manifest has the wrong record_kind")
    if not isinstance(manifest.get("entries"), list):
        raise GateFailure("publication manifest has no entry list")
    return manifest


def write_manifest(root: Path, manifest: dict) -> Path:
    target = root / MANIFEST_NAME
    target.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return target
