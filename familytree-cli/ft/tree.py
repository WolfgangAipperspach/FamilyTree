"""Tree discovery and control file management."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

FAMILYTREE_VERSION = "0.0.1"
_CONTROL_FILE = ".familytree.json"
_CACHE_DIR = ".familytree"


class TreeNotFoundError(Exception):
    """Raised when no .familytree.json can be found walking up from a directory."""


class TreeExistsError(Exception):
    """Raised when trying to init a tree that already exists."""


def find_tree_root(start: Path) -> Path:
    """Walk up from *start* until .familytree.json is found.

    Raises TreeNotFoundError if the file is not found before the filesystem root.
    """
    current = start.resolve()
    while True:
        candidate = current / _CONTROL_FILE
        if candidate.exists():
            return current
        parent = current.parent
        if parent == current:
            raise TreeNotFoundError(
                f"No {_CONTROL_FILE} found in {start} or any parent directory."
            )
        current = parent


def load_control(root: Path) -> dict:
    """Load and return the control file as a dict."""
    control_path = root / _CONTROL_FILE
    with control_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def save_control(root: Path, data: dict) -> None:
    """Write the control file as pretty JSON with a trailing newline."""
    control_path = root / _CONTROL_FILE
    with control_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def init_tree(path: Path) -> dict:
    """Initialise a new tree at *path*.

    Creates:
      - .familytree.json
      - persons/
      - relations/
      - .familytree/

    Raises TreeExistsError if .familytree.json already exists.
    Returns the control-file dict.
    """
    path = path.resolve()
    control_path = path / _CONTROL_FILE
    if control_path.exists():
        raise TreeExistsError(f"A family tree already exists at {path}")

    path.mkdir(parents=True, exist_ok=True)
    (path / "persons").mkdir(exist_ok=True)
    (path / "relations").mkdir(exist_ok=True)
    (path / _CACHE_DIR).mkdir(exist_ok=True)

    tree_uuid = str(uuid.uuid4())
    data: dict = {
        "format": "familytree",
        "familytree_version": FAMILYTREE_VERSION,
        "uuid": tree_uuid,
        "not_duplicates": [],
    }
    save_control(path, data)
    return data
