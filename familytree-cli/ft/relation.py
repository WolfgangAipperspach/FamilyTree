"""Relation CRUD operations."""

from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


_RELATION_FILE = ".relation.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def scan_relations(root: Path) -> Iterator[tuple[dict, Path]]:
    """Yield (data, path) for every .relation.json under relations/."""
    relations_dir = root / "relations"
    if not relations_dir.exists():
        return
    for rel_file in relations_dir.rglob(_RELATION_FILE):
        try:
            with rel_file.open(encoding="utf-8") as fh:
                data = json.load(fh)
            yield data, rel_file
        except (json.JSONDecodeError, OSError):
            continue


def find_relation(root: Path, relation_uuid: str) -> tuple[dict, Path] | None:
    """Return (data, path) for the relation with the given UUID, or None."""
    for data, path in scan_relations(root):
        if data.get("uuid") == relation_uuid:
            return data, path
    return None


def save_relation(folder: Path, data: dict) -> None:
    """Write a relation record as pretty JSON with trailing newline."""
    folder.mkdir(parents=True, exist_ok=True)
    rel_file = folder / _RELATION_FILE
    with rel_file.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def new_relation(
    root: Path,
    rel_type: str,
    folder: Path | None = None,
    **kwargs,
) -> tuple[dict, Path]:
    """Create a new relation record.

    Returns (data, relation_file_path).
    """
    from ft.tree import FAMILYTREE_VERSION

    rel_uuid = str(uuid.uuid4())
    now = _now_iso()
    data: dict = {
        "uuid": rel_uuid,
        "familytree_version": FAMILYTREE_VERSION,
        "type": rel_type,
        "created": now,
        "changed": now,
    }
    data.update(kwargs)

    if folder is None:
        slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", rel_type).lower()
        base = root / "relations" / slug
        candidate = base
        counter = 1
        while (candidate / _RELATION_FILE).exists():
            candidate = Path(f"{base}_{counter}")
            counter += 1
        folder = candidate

    save_relation(folder, data)
    return data, folder / _RELATION_FILE


def touch_relation(data: dict) -> dict:
    """Return a copy of *data* with the *changed* field updated to now."""
    updated = dict(data)
    updated["changed"] = _now_iso()
    return updated


def delete_relation(root: Path, relation_uuid: str) -> Path | None:
    """Remove the relation folder entirely. Returns the deleted folder or None."""
    result = find_relation(root, relation_uuid)
    if result is None:
        return None
    _data, rel_file = result
    folder = rel_file.parent
    shutil.rmtree(folder)
    return folder


def relations_for_person(root: Path, person_uuid: str) -> list[tuple[dict, Path]]:
    """Return all relations that involve the given person UUID."""
    results: list[tuple[dict, Path]] = []
    for data, path in scan_relations(root):
        rel_type = data.get("type")
        involved = False
        if rel_type == "filiation":
            involved = data.get("parent") == person_uuid or data.get("child") == person_uuid
        elif rel_type == "partner":
            involved = person_uuid in (data.get("persons") or [])
        elif rel_type == "association":
            involved = data.get("from") == person_uuid or data.get("to") == person_uuid
        if involved:
            results.append((data, path))
    return results
