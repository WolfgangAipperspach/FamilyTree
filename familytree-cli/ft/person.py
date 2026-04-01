"""Person CRUD operations."""

from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


_PERSON_FILE = ".person.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _name_slug(name: dict) -> str:
    """Produce a filesystem-friendly folder name from a name dict."""
    parts = []
    if name.get("given"):
        parts.append(name["given"])
    if name.get("surname"):
        parts.append(name["surname"])
    slug = "_".join(parts) if parts else "unknown"
    slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_").lower()
    return slug or "unknown"


def scan_persons(root: Path) -> Iterator[tuple[dict, Path]]:
    """Yield (data, path) for every .person.json under persons/."""
    persons_dir = root / "persons"
    if not persons_dir.exists():
        return
    for person_file in persons_dir.rglob(_PERSON_FILE):
        try:
            with person_file.open(encoding="utf-8") as fh:
                data = json.load(fh)
            yield data, person_file
        except (json.JSONDecodeError, OSError):
            continue


def find_person(root: Path, person_uuid: str) -> tuple[dict, Path] | None:
    """Return (data, path) for the person with the given UUID, or None."""
    for data, path in scan_persons(root):
        if data.get("uuid") == person_uuid:
            return data, path
    return None


def save_person(folder: Path, data: dict) -> None:
    """Write a person record as pretty JSON with trailing newline."""
    folder.mkdir(parents=True, exist_ok=True)
    person_file = folder / _PERSON_FILE
    with person_file.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def new_person(
    root: Path,
    name: dict,
    folder: Path | None = None,
    **kwargs,
) -> tuple[dict, Path]:
    """Create a new person record.

    Generates a UUID v4, sets created/changed, picks a folder from the name
    slug if *folder* is not given (appending a counter to avoid collisions).
    Returns (data, person_file_path).
    """
    from ft.tree import FAMILYTREE_VERSION

    person_uuid = str(uuid.uuid4())
    now = _now_iso()
    data: dict = {
        "uuid": person_uuid,
        "familytree_version": FAMILYTREE_VERSION,
        "name": name,
        "created": now,
        "changed": now,
    }
    data.update(kwargs)

    if folder is None:
        slug = _name_slug(name)
        base = root / "persons" / slug
        candidate = base
        counter = 1
        while (candidate / _PERSON_FILE).exists():
            candidate = Path(f"{base}_{counter}")
            counter += 1
        folder = candidate

    save_person(folder, data)
    return data, folder / _PERSON_FILE


def touch_person(data: dict) -> dict:
    """Return a copy of *data* with the *changed* field updated to now."""
    updated = dict(data)
    updated["changed"] = _now_iso()
    return updated


def delete_person(root: Path, person_uuid: str) -> Path | None:
    """Remove the person folder entirely. Returns the deleted folder or None."""
    result = find_person(root, person_uuid)
    if result is None:
        return None
    _data, person_file = result
    folder = person_file.parent
    shutil.rmtree(folder)
    return folder
